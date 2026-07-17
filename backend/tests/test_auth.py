import asyncio
from auth import hash_password, verify_password_async, create_access_token
from jose import jwt
from config import settings


class TestHashPassword:
    def test_hash_and_verify(self):
        password = "my_secret_123"
        hashed = hash_password(password)
        assert hashed != password
        assert asyncio.get_event_loop().run_until_complete(
            verify_password_async(password, hashed)
        ) is True

    def test_wrong_password(self):
        hashed = hash_password("correct_password")
        assert asyncio.get_event_loop().run_until_complete(
            verify_password_async("wrong_password", hashed)
        ) is False

    def test_different_hashes(self):
        """Same password should produce different hashes (salt)."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2
        # But both should verify
        loop = asyncio.get_event_loop()
        assert loop.run_until_complete(verify_password_async("same_password", h1)) is True
        assert loop.run_until_complete(verify_password_async("same_password", h2)) is True


class TestCreateAccessToken:
    def test_valid_token(self):
        data = {"sub": "test-user-id"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test-user-id"
        assert "exp" in payload

    def test_token_contains_data(self):
        data = {"sub": "user-123", "role": "admin"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
