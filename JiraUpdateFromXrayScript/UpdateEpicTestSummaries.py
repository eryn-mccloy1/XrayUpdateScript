"""
File: UpdateEpicTestSummaries.py
Author: Eryn McCloy
Date: 1/10/2025
Description: This script will update the Test Summary on all Jira epics for the current release. This includes updating the following fields: Total Tests, Tests Executed, Tests Passed, Tests Remaining, and Release-able %.
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

print(f"Updated the test summary on {epicsUpdated} epics.")
print("Complete")  