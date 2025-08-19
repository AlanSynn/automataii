from typing import Any


class AppConfig:
    """
    Configuration File
    """

    APP_NAME: str = "Automata Designer"

    @classmethod
    def initialize(cls) -> None:
        """
        Perform any necessary initializations here, e.g.:
        - Loading settings from a file
        """

    def get_var(self) -> Any:
        """
        Get the Var.
        """

    def set_var(self, value: Any) -> Any:
        """
        Set the Var.
        """
