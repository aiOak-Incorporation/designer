from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        user_identifier = (username or "").strip()
        if not user_identifier:
            return None

        UserModel = get_user_model()
        # Fetch all potential matches by username or email (case-insensitive)
        candidate_users_qs = UserModel.objects.filter(
            Q(username__iexact=user_identifier) | Q(email__iexact=user_identifier)
        ).order_by("-is_active", "-last_login", "id")

        # Iterate all candidates and return the first whose password matches
        for candidate_user in candidate_users_qs:
            if not self.user_can_authenticate(candidate_user):
                continue
            if candidate_user.check_password(password):
                return candidate_user

        # No matching user/password combination found
        return None
