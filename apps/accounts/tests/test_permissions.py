from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.accounts.permissions import IsAdminRole,IsContributorRole
from apps.accounts.models import User

class RolePermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.admin = User(
            email ='admin@test.com',
            role='admin'
        )

        self.contributor = User(
            email ='contributor@test.com',
            role='contributor'
        )

    def check_permissions(self,permission_class,user):
        request = self.factory.get('/')
        force_authenticate(request,user=user)
        return permission_class().has_permission(request,None)

    def test_admin_permission(self):
        self.assertTrue(
            self.check_permissions(IsAdminRole,self.admin)
        )

    def test_contributor_denied_admin_permission(self):
        self.assertFalse(
            self.check_permissions(IsAdminRole,self.contributor)
        )