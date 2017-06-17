#!usr/bin/python
import sys
import PySalesforce

def main():
    filename = ''
    loginUsername = ''
    loginPassword = '' # this should be the password + token
    loginClientId = ''
    loginClientSecret = ''
    isProduction = True
    isProductionValFound = False
    
    # get arguments
    i = 0 
    for i in range(0, len(sys.argv)):
        arg = sys.argv[i]

        if arg == '-f' or arg == '--file':
            i += 1
            filename = sys.argv[i]
        elif arg == '-un' or arg == '--username':
            i += 1
            loginUsername = sys.argv[i]
        elif arg == '-pw' or arg == '--password':
            i += 1
            loginPassword = sys.argv[i]
        elif arg == '-cid' or arg == '--clientid':
            i += 1
            loginClientId = sys.argv[i]
        elif arg == '-cs' or arg == '--clientsecret':
            i += 1
            loginClientSecret = sys.argv[i]
        elif arg == '-ipr' or arg == '--isProduction':
            i+= 1
            isProductionValFound = True

            if sys.argv[i].lower() == 'false':
                isProduction = False

    # check for missing arguments and return error if any are missing
    errors = 'Missing arguments: '
    if filename == '':
        errors += 'filename, '
    if loginUsername == '':
        errors += 'username, '
    if loginPassword == '':
        errors += 'password, '
    if loginClientId == '':
        errors += 'client id, '
    if loginClientSecret == '':
        errors += 'client secret, '
    if isProductionValFound == False:
        errors += 'is production, '

    if errors != 'Missing arguments: ':
        errors += 'all arguments must be provided.'
        print(errors)
        sys.exit(1)

    # log in to Salesforce to get token and instance url
    loginResponse = PySalesforce.Authentication.getOAuthLogin(loginUsername, loginPassword, loginClientId, loginClientSecret, isProduction)

    accessToken = loginResponse['access_token']
    instanceUrl = loginResponse['instance_url']

    # get the code file, and run the anonymous code
    codeFile = open(filename, "r").read()
    executeResponse = PySalesforce.Tooling.executeAnonymous(codeFile, accessToken, instanceUrl)
    
    print('execute code response: {}'.format(executeResponse))

    logoutResponse = PySalesforce.Authentication.getOAuthLogout(accessToken, isProduction)

    print('logout response: {}'.format(logoutResponse))

if __name__ == "__main__":
    main()