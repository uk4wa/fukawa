# from unittest.mock import Mock
# from pytest_mock import MockFixture


# def test_mock(mocker: MockFixture):
#     mock_response: Mock = mocker.Mock()
#     mock_response.json.return_value = {"id": 1}

#     mock_get = mocker.patch("pet.app.ap.requests.get", return_value=mock_response)
#     result = get_url_request(1)

#     assert result == {"id": 1}
#     mock_get.assert_called_once_with("https://api.example.com/users/1")


# i: int = 0


# @pytest.fixture(scope="session")
# def fixture():
#     global i
#     i += 1
#     db = f"db{i}"
#     print(f"DB [[[[[[[[[[[INITED--{i}]]]]]]]]]]]")
#     yield db
#     db = None
#     print(f"DB [[[[[[[[[[[CLOSED--{i}]]]]]]]]]]]")