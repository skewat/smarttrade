from SmartApi import SmartConnect
import config
from logzero import logger 
import pyotp

def connect():
    ''' Connect to AngelOne using API '''
    smartApi = SmartConnect(config.API_KEY)
    try:
        token = config.TOKEN
        totp = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e

    correlation_id = "abcde"
    data = smartApi.generateSession(config.USERNAME, config.PWD, totp)

    if data['status'] == False:
        logger.error(data)

    else:
        # login api call
        authToken = data['data']['jwtToken']
        refreshToken = data['data']['refreshToken']
        # fetch the feedtoken
        feedToken = smartApi.getfeedToken()
        # fetch User Profile
        res = smartApi.getProfile(refreshToken)
        smartApi.generateToken(refreshToken)
        res = res['data']['exchanges']
        print("\n\n\n")
        return smartApi

def logout(smartAPi):
    # logout from AngenOne API
    try:
        logout = smartApi.terminateSession('AAAE362329')
        print("\n\n\n")
        logger.info("Logout Successfull")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")

