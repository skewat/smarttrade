from SmartApi import SmartConnect
import config
from logzero import logger 
import pyotp


class AngelOneConnector:
    def __init__(self):
        self.smart_api = None
        self.feed_token = None
        self.refresh_token = None
        self.auth_token = None

    def connect(self):
        '''Connect to AngelOne using SmartAPI'''
        try:
            self.smart_api = SmartConnect(api_key=config.API_KEY)

            totp = pyotp.TOTP(config.TOKEN).now()
            login_data = self.smart_api.generateSession(config.USERNAME, config.PWD, totp)

            if not login_data.get("status"):
                logger.error(f"Login failed: {login_data}")
                raise Exception("Login failed")

            self.auth_token = login_data["data"]["jwtToken"]
            self.refresh_token = login_data["data"]["refreshToken"]
            self.feed_token = self.smart_api.getfeedToken()

            profile = self.smart_api.getProfile(refreshToken=self.refresh_token)
            logger.info(f"Login successful.... ")

        except Exception as e:
            logger.exception("AngelOne connection failed.")
            raise e

    def is_token_valid(self):
        '''Check if the current access token is still valid'''
        if not self.smart_api or not self.refresh_token:
            logger.warning("SmartAPI client or refresh token not initialized.")
            return False

        try:
            profile = self.smart_api.getProfile(refreshToken=self.refresh_token)
            return profile.get("status") is True
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return False

    def logout(self):
        '''Logout from AngelOne API'''
        try:
            if self.smart_api:
                self.smart_api.terminateSession(config.USERNAME)
                logger.info("Logout successful")
        except Exception as e:
            logger.exception(f"Logout failed: {e}")

    def get_feed_token(self):
        return self.feed_token

    def get_refresh_token(self):
        return self.refresh_token

    def get_smart_api(self):
        return self.smart_api

