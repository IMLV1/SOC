import pytest
from pydantic import ValidationError

from app.auth.google_routes import GoogleStartInput
from app.auth.models import LoginInput, RegisterInput


@pytest.mark.parametrize("length", [6, 10, 12])
def test_registration_accepts_requested_boundaries(length: int) -> None:
    body = RegisterInput.model_validate(
        {"email": "learner@example.test", "display_name": "Learner", "password": "x" * length}
    )
    assert len(body.password) == length


@pytest.mark.parametrize("length", [0, 4, 5, 13, 129])
def test_registration_rejects_out_of_range_passwords(length: int) -> None:
    with pytest.raises(ValidationError):
        RegisterInput.model_validate(
            {"email": "learner@example.test", "display_name": "Learner", "password": "x" * length}
        )


def test_existing_long_passwords_remain_valid_for_login_and_google_link() -> None:
    previous_password = "x" * 128
    login = LoginInput(email="learner@example.test", password=previous_password)
    google_link = GoogleStartInput(purpose="link", password=previous_password)
    assert login.password == previous_password
    assert google_link.password == previous_password
    assert LoginInput(email="learner@example.test", password="x" * 5).password == "x" * 5
    assert GoogleStartInput(purpose="link", password="x" * 5).password == "x" * 5


@pytest.mark.parametrize("length", [4, 129])
def test_login_and_google_link_reject_out_of_range_passwords(length: int) -> None:
    with pytest.raises(ValidationError):
        LoginInput(email="learner@example.test", password="x" * length)
    with pytest.raises(ValidationError):
        GoogleStartInput(purpose="link", password="x" * length)
