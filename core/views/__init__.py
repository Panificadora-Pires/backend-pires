from .token import CustomTokenObtainPairView, CustomTokenRefreshView, CustomTokenVerifyView
from .user import UserRegistrationView, UserViewSet
from .invite import AdminInviteCreateView, AdminInviteRegistrationView
from .social import CustomGoogleLoginView

all = [
    'CustomTokenObtainPairView',
    'CustomTokenRefreshView',
    'CustomTokenVerifyView',
    'UserRegistrationView',
    'UserViewSet',
    'AdminInviteCreateView',
    'AdminInviteRegistrationView',
    'CustomGoogleLoginView',
]