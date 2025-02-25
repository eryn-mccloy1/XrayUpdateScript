"""
File: updateJiraEpicsFromXray.py
Author: Eryn McCloy
Date: 1/10/2025
Description: This script will update Xray Tests with the most recent test statuses from Nextworld. The tests to be updated as well as the Nextworld environment used to gather test results from is configurable in the config.json file. Additionally, this script will update the Test Summary on all Jira epics for the current release. This includes updating the following fields: Total Tests, Tests Executed, Tests Passed, Tests Remaining, and Release-able %.
"""

import pip._vendor.requests
from pip._vendor.requests.auth import HTTPBasicAuth
import json
with open('JiraUpdateFromXrayScript/config.json', 'r') as file:
    config = json.load(file)

print("Running")
#JIRA API VARIABLES
jiraAuth = HTTPBasicAuth(config["JIRA_EMAIL"], config["JIRA_AUTH_TOKEN"])

jiraRequestHeader = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

#XRAY API VARIABLES
getXrayAccessTokenResponse = pip._vendor.requests.post(
    "https://xray.cloud.getxray.app/api/v2/authenticate",
    json={
        "client_id": config["XRAY_CLIENT_ID"],
        "client_secret": config["XRAY_CLIENT_SECRET"]
    },
)
xrayAccessToken = getXrayAccessTokenResponse.json()
xrayRequestHeader = {
    "Authorization": f'Bearer {xrayAccessToken}'
}
if not getXrayAccessTokenResponse.ok or xrayAccessToken == None:
    print("Error getting Xray access token. Check credentials and network connection.")
    print(xrayAccessToken)
    exit()

#NEXTWORLD API VARIABLES
nextworldAuth = HTTPBasicAuth(config["NEXTWORLD_EMAIL"], config["NEXTWORLD_PASSWORD"])

nextworldRequestHeader = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

getNextworldAccessTokenResponse = pip._vendor.requests.request(
   "POST",
   "https://auth1.nextworld.net/v2/Authenticate/Tokens",
      json={
       "Zone": config["NEXTWORLD_ENVIRONMENT"],
   },
   headers=nextworldRequestHeader,
   auth=nextworldAuth
)

if not getNextworldAccessTokenResponse.ok:
    print("Error getting Nextworld access token. Check credentials and network connection. Check that two factor authentication is disabled for the user in Nextworld.")
    print(getNextworldAccessTokenResponse.json())
    exit()

nextworldRequestHeaderWithToken = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f'Bearer {getNextworldAccessTokenResponse.json().get("access_token")}'
}
testSuitesNotFound = []
testSummariesNotFound = []
testsFound = 0
# For each execution specified in the config file:
for testExecution in config["AUTOMATED_TEST_EXECUTIONS"]:

    # Get the all the tests in the execution. Xray can only return 100 tests at a time, so if the execution contains more than 100 we will loop until all tests have been updated
    totalTestsInExecution = 0
    testsCounted = 0
    while True:
        getAutomatedTestExecution = pip._vendor.requests.post(
            url="https://xray.cloud.getxray.app/api/v2/graphql",
            headers=xrayRequestHeader,
            data={'query': f"""{{getTestExecution(issueId: "{testExecution}") {{tests(limit: 100, start: {testsCounted}) {{total limit results {{issueId jira(fields: ["customfield_10505", "summary"])}}}}}}}}"""}
        )

        if not getAutomatedTestExecution.ok or getAutomatedTestExecution.json().get('data').get('getTestExecution') is None:
            print("Error getting Xray automated test execution. Check that the config file has the correct test execution id")
            print(getAutomatedTestExecution.json())
            exit()    

        totalTestsInExecution = getAutomatedTestExecution.json().get('data').get('getTestExecution').get('tests').get('total')

        # Add all test ids to a list
        automatedTestExecutionAllTests = getAutomatedTestExecution.json().get('data').get('getTestExecution').get('tests').get('results')
        testIssueIds = []
        testSuiteNameWithTestSummary = {}
        for test in automatedTestExecutionAllTests:
            testIssueIds.append(test['issueId'])
            testSuiteNameWithTestSummary[test['jira']['summary']] = test['jira']['customfield_10505']

        # format the list of test ids into a string separated by commas. This will be used in the request to get all test runs at once. 
        testIssueIdsFormatted = ", ".join(f'"{id}"' for id in testIssueIds)

        # Get the test runs
        getTestRunResponse = pip._vendor.requests.post(
            url="https://xray.cloud.getxray.app/api/v2/graphql",
            headers=xrayRequestHeader,
            data={'query': f"""{{getTestRuns(testIssueIds: [{testIssueIdsFormatted}],testExecIssueIds: ["{testExecution}"],limit: 100) {{total results {{id test {{jira(fields: ["customfield_10505"])}}}}}}}}"""}
        )

        if not getTestRunResponse.ok:
            print("Error getting Xray test runs.")
            print(getTestRunResponse.json())
            exit()
        
        # Add test run ids to a dict with the run id as the key. Additionally, add the test suite names to a list to be used in the Nextworld request
        testRunIds = {}
        testSuiteNames = []
        testRuns = getTestRunResponse.json().get('data').get('getTestRuns').get('results')
        for testRun in testRuns:
            testSuiteNameOnXrayTest = testRun.get('test').get('jira').get('customfield_10505')
            if (testSuiteNameOnXrayTest):
                testRunIds[testRun.get('id')] = testSuiteNameOnXrayTest
                testSuiteNames.append(testSuiteNameOnXrayTest)
                testsFound += 1

        # Get Nextworld results for all test suites
        testSuiteNamesFormatted = ", ".join(json.dumps(name) for name in testSuiteNames)
        body = f'{{"testSuiteNames" : [{testSuiteNamesFormatted}]}}'
        nextworldGetTestResultsResponse = pip._vendor.requests.request(
            "POST",
            f"{config['NEXTWORLD_URL']}/api/data/v1/automated-testing/test-suites:getLatestResultsForSuites",
            headers=nextworldRequestHeaderWithToken,
            data=body.encode('utf-8')
        )
        nextworldGetTestResultsResponseJson = nextworldGetTestResultsResponse.json()

        if not nextworldGetTestResultsResponse.ok:
            print("Error getting Nextworld test results. Check that the Nextworld endpoint '/v1/automated-testing/test-suites/test-results:getLatestNightlyRunTestResults' is working")
            print(nextworldGetTestResultsResponseJson)
            exit()

        numberOfTests = len(nextworldGetTestResultsResponseJson)
        testSuiteStatuses = {}
        for x in range(numberOfTests):

            # Convert the Nextworld test status to the Xray test status.
            nextworldTestStatus = nextworldGetTestResultsResponseJson[x].get('TestResultStatus')
            xrayTestStatus = None
            if nextworldTestStatus == 'Initialized':
                xrayTestStatus = 'TO DO'
            if nextworldTestStatus == 'Running':
                xrayTestStatus = 'EXECUTING'
            if nextworldTestStatus == 'Success':
                xrayTestStatus = 'PASSED'
            if nextworldTestStatus == 'Failure':
                xrayTestStatus = 'FAILED'
            if nextworldTestStatus == 'Skipped':
                xrayTestStatus = 'BLOCKED'
            if nextworldTestStatus == 'FailedSystemErrors':
                xrayTestStatus = 'FAILED-RELEASEABLE'
            if nextworldTestStatus == 'Failed to Run':
                xrayTestStatus = 'FAILED'
            if nextworldTestStatus is None:
                testSuitesNotFound.append(nextworldGetTestResultsResponseJson[x].get('TestSuiteName'))
            
            testSuiteStatuses[nextworldGetTestResultsResponseJson[x].get('TestSuiteName')] = xrayTestStatus

        # Add any test suites not found to a list so it can be reported to the user
        for test_summary, test_suite in testSuiteNameWithTestSummary.items():
            if test_suite in testSuitesNotFound:
                testSummariesNotFound.append(test_summary)

        # Merge the testRunIds dict with the testStatuses dict to create a dict with Test Run Id: Test Status
        runIdStatuses = {}
        for run_id, suite_name in testRunIds.items():
            suite_result = testSuiteStatuses[suite_name]
            runIdStatuses[run_id] = suite_result

        # Build the data for the updateTestRun request. An alias is required for each instance of updateTestRunStatus().
        updateTestRunData = ""
        aliasIncrement=0
        for testRunId, testRunStatus  in runIdStatuses.items():
            aliasIncrement+=1
            updateTestRunData +=  "Alias"+str(aliasIncrement)+": "+f"""updateTestRunStatus(id: "{testRunId}", status: "{testRunStatus}")"""

        #Update the test runs with the new status
        updateTestRunResponse = pip._vendor.requests.post(
            url="https://xray.cloud.getxray.app/api/v2/graphql",
            headers=xrayRequestHeader,
            data= {'query': f"""mutation {{{updateTestRunData}}}"""}
        )

        if not updateTestRunResponse.ok:
            print("Error updating Xray test runs.")
            print(updateTestRunResponse.json())
            exit()

        # Increment testsCounted and check if all the tests have been counted. If so, break out of the loop.
        testsCounted += 100
        if testsCounted >= totalTestsInExecution:   
            break

# Now that test automation test statuses have been updated, count up the test result totals for each execution to update the epic test summary
# Get all epics in the release from Jira
getJiraEpicsResponse = pip._vendor.requests.request(
   "GET",
   "https://nextworldproduction.atlassian.net/rest/api/3/search",
   headers=jiraRequestHeader,
   params={'jql': f'project IN (APP, BOT, CI) AND statuscategory != done AND type = Epic AND fixversion = "{config["CURRENT_RELEASE"]}"','maxResults': '500','fields': 'key'},
   auth=jiraAuth
)
if not getJiraEpicsResponse.ok:
    print("Error getting Jira epics. Check that your Jira credentials are correct. Check that the config file has the correct release name.")
    print(getJiraEpicsResponse.json())
    exit()

# For each epic in the release, get the associated Xray Test Execution
jiraEpics = getJiraEpicsResponse.json().get('issues')
numberOfEpicsFound = len(jiraEpics)
epicsUpdated = 0 
for epicIteration in range(numberOfEpicsFound):
  
    epicKey = jiraEpics[epicIteration].get('key')
    totalTestsInExecution = 0
    testsCounted = 0
    totalTests = 0
    passedTests = 0
    executedTests = 0
    remainingTests = 0
    releasablePercent = 0
    failedReleasableTests = 0

    # Xray only returns 100 tests at a time, so we need to loop through the results until we've looked at all the tests. 
    # The API query uses start:"testsCounted" which will increment by 100 each time until all tests are counted.
    while True:
        getTestExecutionResponse = pip._vendor.requests.post(
            url="https://xray.cloud.getxray.app/api/v2/graphql",
            headers=xrayRequestHeader,
            data={'query': f"""{{getTestExecutions(jql: "parent = '{epicKey}'", limit: 1) {{results {{issueId tests(limit: 100, start: {testsCounted}) {{total results {{issueId jira(fields: ["customfield_10505", "summary"]) status {{name}}}}}}}}}}}}"""}
        )

        if not getTestExecutionResponse.ok:
            print(f"Error getting Xray test execution for epic {epicKey}")
            print(getTestExecutionResponse.json())
            exit()
        
        # If no test execution is found, skip to the next epic
        testExecution = getTestExecutionResponse.json().get('data').get('getTestExecutions').get('results')
        if len(testExecution) == 0:
            break

        # Loop through each test returned and add the test id to a list. This will be used in the request to get all test runs at once.
        testExecutionId = testExecution[0]['issueId']
        totalTestsInExecution = testExecution[0]['tests']['total']
        testExecutionAllTests = testExecution[0]['tests']['results']
        testIssueIds = []
        for test in testExecutionAllTests:
            testIssueIds.append(test['issueId'])

        # Format the list of test ids into a string separated by commas.
        testIssueIdsFormatted = ", ".join(f'"{id}"' for id in testIssueIds)

        # Get the test runs
        getTestRunResponse = pip._vendor.requests.post(
            url = "https://xray.cloud.getxray.app/api/v2/graphql",
            headers = xrayRequestHeader,
            data = {'query': f"""{{getTestRuns(testIssueIds: [{testIssueIdsFormatted}],testExecIssueIds: ["{testExecutionId}"],limit: 100) {{total results {{id status {{name}}}}}}}}"""}
        )

        if not getTestRunResponse.ok:
            print("Error getting Xray test runs.")
            print(getTestRunResponse.json())
            exit()

        # Count up the statuses of each test run
        testRuns = getTestRunResponse.json().get('data').get('getTestRuns').get('results')
        for testRun in testRuns:
            xrayTestStatus = testRun.get('status').get('name')
            totalTests += 1
            if xrayTestStatus == 'PASSED':
                passedTests += 1
                executedTests += 1
            elif xrayTestStatus == 'TO DO':
                remainingTests += 1
            elif xrayTestStatus == 'EXECUTING':
                remainingTests += 1
            elif xrayTestStatus == 'FAILED':
                executedTests += 1
            elif xrayTestStatus == 'FAILED-RELEASEABLE': 
                executedTests += 1
                failedReleasableTests += 1
            elif xrayTestStatus == 'BLOCK-RELEASE':
                executedTests += 1

        # Increment testsCounted and check if all the tests have been counted. If so, break out of the loop.
        testsCounted += 100
        if testsCounted >= totalTestsInExecution:
            break
        
    # Once all tests have been counted, update the epic in Jira with the test results
    if len(testExecution) != 0:
        if totalTests != 0:
            releasablePercent = ((failedReleasableTests + passedTests) / totalTests) * 100
        epicsUpdated += 1
        updateJiraEpicResponse = pip._vendor.requests.request(
            "PUT",
            f"https://nextworldproduction.atlassian.net/rest/api/3/issue/{epicKey}",
            data=json.dumps( {"fields": {"customfield_10120": totalTests,"customfield_10122": passedTests,"customfield_10121": executedTests,"customfield_10123": remainingTests, "customfield_10127": str(releasablePercent)}} ),
            headers=jiraRequestHeader,
            auth=jiraAuth
        )

        if not updateJiraEpicResponse.ok:
            print(f"Error updating Jira epic {epicKey}")
            print(updateJiraEpicResponse.json())


if testSummariesNotFound:
    print(f"The following {len(testSummariesNotFound)} tests in Xray have the Test Suite Name field populated, but the test suite was not found in Nextworld. Please check that the Test Suite Name field in Xray is correct and that the suite in Nextworld is active in the selected environment:")
    for test in testSummariesNotFound:
         print(test)
    print()

print(f"Updated {testsFound - len(testSummariesNotFound)} tests with their latest test result from Nextworld")
print(f"Updated the test summary on {epicsUpdated} epics.")
print("Complete")  