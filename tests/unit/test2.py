# import pytest


# class AppError(Exception):
#     message: str

#     def __init__(self, message: str) -> None:
#         super().__init__(message)
#         self.message = message


# def check_num(x: int):
#     if x > 5 and x < 10:
#         raise AppError(message="x between 4 and 10")


# # @pytest.mark.skipif(5 == 5, reason="by")
# @pytest.mark.parametrize("x", [6, 7, 8, 9], ids=lambda v: f"error value {v}")
# def test_error(x: int, fixture: str):
#     with pytest.raises(AppError, match="x between 4 and 10"):
#         check_num(x)
