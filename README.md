# XrayUpdateScript
This script will update Xray Tests with the most recent test statuses from Nextworld. The tests to be updated as well as the Nextworld environment used to gather test results from is configurable in the config.json file. Additionally, this script will update the Test Summary on all Jira epics for the current release. This includes updating the following fields: Total Tests, Tests Executed, Tests Passed, Tests Remaining, and Release-able %.


The following fields will need to be entered in the config file for the script to work:

CURRENT_RELEASE = The name of the current release in Jira. We will only update the test summaries for epics with fix versions of this release. For example, "Cassiopeia (25.1)".

AUTOMATED_TEST_EXECUTIONS = The KEY ID of the test execution(s) that contain automated tests. These are the executions that will be updated with the latest results in Nextworld. (Note - to get the issue key in Jira, use the action "export XML". The issue key looks like "123456" NOT "APP-24124")

JIRA_EMAIL = the email you use to log in to Jira

JIRA_AUTH_TOKEN = create a Jira api token here. Name doesn’t matter. https://id.atlassian.com/manage-profile/security/api-tokens

XRAY_CLIENT_ID= Ask an Xray admin to create a API key for your Jira user. 

NEXTWORLD_EMAIL = the email you use to log in to Nextworld

NEXTWORLD_PASSWORD = the password you use to log in to Nextworld Dev (User should have access to the environment being used to retrieve test results. User should have two factor auth turned off)

NEXTWORLD_ENVIRONMENT = The Nextworld environment and tenant where the test results should be retrieved from. Formatted like “tenant”-”environment”. For example: “autotest-QATesting.master”

NEXTWORLD_URL = The endpoint URL of the Nextworld environment where the test results should be retrieved from. For example: “https://api-qatestingmaster.nextworld.net”. 
