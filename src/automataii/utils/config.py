class AppConfig:
    """
    Configuration File
    """

    APP_NAME: str = "MotionSmith"
    APP_VERSION: str = "0.1.6"
    ORGANIZATION_NAME: str = "MotionSmith"
    ORGANIZATION_DOMAIN: str = "motionsmith.app"

    @classmethod
    def initialize(cls) -> None:
        """
        Perform any necessary initializations here, e.g.:
        - Loading settings from a file
        """
