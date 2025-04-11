"""
File: UpdateXrayTestsWithLatestStatus.py
Author: Eryn McCloy
Date: 1/10/2025
Description: This script will update Xray Tests with the most recent test statuses from Nextworld. The tests to be updated as well as the Nextworld environment used to gather test results is configurable in the config.json file. 
"""

import pip._vendor.requests
from pip._vendor.requests.auth import HTTPBasicAuth
import json
from itertools import islice
with open('JiraUpdateFromXrayScript/config.json', 'r') as file:
    config = json.load(file)

print("Running")

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
if config["RELEASE_PIPELINE_ID"] is not None and config["RELEASE_PIPELINE_ID"] != "":
    releaseId = config["RELEASE_PIPELINE_ID"].replace(".", "")
    nextworldAuthServerURL = f"https://auth-nw{releaseId}dev.releasepipeline.nextworld.net/v2/Authenticate/Tokens"
else:
    nextworldAuthServerURL = "https://auth1.nextworld.net/v2/Authenticate/Tokens"

def get_nextworld_request_header_with_token():
    getNextworldAccessTokenResponse = pip._vendor.requests.request(
    "POST",
    nextworldAuthServerURL,
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

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f'Bearer {getNextworldAccessTokenResponse.json().get("access_token")}'
    }

nextworldRequestHeaderWithToken = get_nextworld_request_header_with_token()
testSuitesNotFound = []
testSummariesNotFound = []
testsFound = 0

# For each execution specified in the config file:
for testExecution in config["AUTOMATED_TEST_EXECUTIONS"]:

    # Get the all the tests in the execution. Xray can only return 100 tests at a time, so if the execution contains more than 100 we will loop until all tests have been updated
    totalTestsInExecution = 0
    testsCounted = 0
    loopCount = 0
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
        testSuiteIssueIdWithTestSummary = {}
        for test in automatedTestExecutionAllTests:
            testIssueIds.append(test['issueId'])
            testSuiteNameWithTestSummary[test['issueId']] = test['jira']['customfield_10505']
            testSuiteIssueIdWithTestSummary[test['issueId']] = test['jira']['summary']

        # format the list of test ids into a string separated by commas. This will be used in the request to get all test runs at once. 
        testIssueIdsFormatted = ", ".join(f'"{id}"' for id in testIssueIds)

        # Get the test runs
        getTestRunResponse = pip._vendor.requests.post(
            url="https://xray.cloud.getxray.app/api/v2/graphql",
            headers=xrayRequestHeader,
            data={'query': f"""{{getTestRuns(testIssueIds: [{testIssueIdsFormatted}],testExecIssueIds: ["{testExecution}"],limit: 100) {{total results {{id test {{jira(fields: ["customfield_10490", "customfield_10505"])}}}}}}}}"""}
        )

        if not getTestRunResponse.ok:
            print("Error getting Xray test runs.")
            print(getTestRunResponse.json())
            continue
        
        # Add test run ids to a dict with the run id as the key. Additionally, add the test suite names to a list to be used in the Nextworld request
        testRunIds = {}
        testSuiteLinks = []
        testRuns = getTestRunResponse.json().get('data').get('getTestRuns').get('results')
        for testRun in testRuns:
            testSuiteNameOnXrayTest = testRun.get('test').get('jira').get('customfield_10505')
            testSuiteLinkOnXrayTest = testRun.get('test').get('jira').get('customfield_10490')

            if testSuiteLinkOnXrayTest:
                testRunIds[testRun.get('id')] = testSuiteLinkOnXrayTest
                testSuiteLinks.append(testSuiteLinkOnXrayTest)
                testsFound += 1

        # Get Nextworld results for all test suites
        testSuiteNamesFormatted = ", ".join(json.dumps(name) for name in testSuiteLinks)
        body = f'{{"testSuiteLinks" : [{testSuiteNamesFormatted}]}}'
        nextworldGetTestResultsResponse = pip._vendor.requests.request(
            "POST",
            f"{config['NEXTWORLD_URL']}/api/automated-testing/v1/test-suites:getLatestResultsForSuitesFromLinks",
            headers=nextworldRequestHeaderWithToken,
            data=body.encode('utf-8')
        )
        nextworldGetTestResultsResponseJson = nextworldGetTestResultsResponse.json()

        if not nextworldGetTestResultsResponse.ok:
            print("Error getting Nextworld test results. Check that the Nextworld endpoint '/v1/automated-testing/test-suites/test-results:getLatestNightlyRunTestResults' is working")
            print(nextworldGetTestResultsResponseJson)
            continue

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
            
            testSuiteStatuses[nextworldGetTestResultsResponseJson[x].get('TestResultLink')] = xrayTestStatus

        # Add any test suites not found to a list so it can be reported to the user
        for test_summary, test_suite in testSuiteNameWithTestSummary.items():
            if test_suite in testSuitesNotFound:
                testUniqueName = testSuiteIssueIdWithTestSummary[test_summary]+" - "+test_summary
                testSummariesNotFound.append(testUniqueName)

        # Merge the testRunIds dict with the testStatuses dict to create a dict with Test Run Id: Test Status
        runIdStatuses = {}
        for run_id, suite_name in testRunIds.items():
            runIdStatuses[run_id] = testSuiteStatuses[suite_name]

        # This particular endpoint only allows 25 updates at a time, so we need to chunk the data into batches of 25
        def chunk_dict(data, size=25):
            it = iter(data)
            for _ in range(0, len(data), size):
                yield {k: data[k] for k in islice(it, size)}

        # Process updates in batches of 25
        for batch in chunk_dict(runIdStatuses, size=25):

            # Build the data for the updateTestRun request. An alias is required for each instance of updateTestRunStatus().
            updateTestRunData = ""
            aliasIncrement=0

            for testRunId, testRunStatus  in batch.items():
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
                print(updateTestRunResponse)

        # Increment testsCounted and check if all the tests have been counted. If so, break out of the loop.
        testsCounted += 100
        if testsCounted >= totalTestsInExecution:   
            break
        # If the loop has run 5 times, get a new access token for Nextworld. This is to prevent the token from expiring during the script execution
        if loopCount % 5 == 0 and loopCount != 0:
            nextworldRequestHeaderWithToken = get_nextworld_request_header_with_token()
        loopCount += 1

if testSummariesNotFound:
    print(f"The following {len(testSummariesNotFound)} tests in Xray have the Test Suite Link field populated, but the test suite was not found in Nextworld. Please check that the Test Suite Link field in Xray is correct and that the suite in Nextworld is active in the selected environment:")
    for test in testSummariesNotFound:
         print(test)
    print()

print(f"Updated {testsFound - len(testSummariesNotFound)} tests with their latest test result from Nextworld")
print("Complete")  