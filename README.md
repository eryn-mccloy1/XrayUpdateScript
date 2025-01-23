# XrayUpdateScript
This script will update the tests in the automated test execution with the most recent test statuses from Nextworld QATesting.master -autotest environment. Additionally, this script will update the Test Summary on all Jira epics for the current release. This includes updating the following fields: Total Tests, Tests Executed, Tests Passed, and Tests Remaining.

Nothing in updateJiraEpicsFromXray.py should ever be updated.
Only ever update the config.json file. 


The following fields will need to be entered in the config file for the script to work:

CURRENT_RELEASE = The name of the current release in Jira. We will only update the test summaries for epics with fix versions of this release. For example, "Cassiopeia (25.1)".

AUTOMATED_TEST_EXECUTIONS = The KEY ID of the test execution(s) that contain automated tests. These are the executions that will be updated with the latest results in Nextworld. (Note - to get the issue key in Jira, use the action "export XML". The issue key looks like "123456" NOT "APP-24124")

JIRA_EMAIL = the email you use to log in to Jira

JIRA_AUTH_TOKEN = create a Jira api token here. Name doesn’t matter. 

XRAY_CLIENT_ID= Ask an Xray admin to create a API key for your Jira user. See documentation for details.

NEXTWORLD_EMAIL = the email you use to log in to Nextworld

NEXTWORLD_PASSWORD = the password you use to log in to Nextworld Dev (user will need access to QATesting.master - autotest)
