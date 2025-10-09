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
        try:
            user = UserModel.objects.get(
                Q(username__iexact=user_identifier) | Q(email__iexact=user_identifier)
            )
        except UserModel.MultipleObjectsReturned:
            user = (
                UserModel.objects.filter(
                    Q(username__iexact=user_identifier) | Q(email__iexact=user_identifier)
                ).first()
            )
        except UserModel.DoesNotExist:
            return None

        if user and self.user_can_authenticate(user) and user.check_password(password):
            return user
        return None
