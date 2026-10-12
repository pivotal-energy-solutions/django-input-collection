"""The Condition admin renders group conditions (no instrument, repeat_group set)."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .checklists import question
from .repeats import answer, doors, group_gate


class GroupConditionAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request, cls.group, _ = doors(count=2)
        answer(question(cls.request, "has-doors", group="Doors", order=0), "yes")
        cls.condition = group_gate(cls.group, "has-doors")
        cls.admin = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_changelist_renders(self):
        response = self.client.get(reverse("admin:django_input_collection_condition_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "repeat: doors")

    def test_change_page_renders(self):
        url = reverse("admin:django_input_collection_condition_change", args=[self.condition.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
