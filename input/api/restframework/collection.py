from django.urls import reverse

from ...collection import BaseAPICollector


class RestFrameworkCollector(BaseAPICollector):
    def get_api_info(self):
        placeholder_pk_kwargs = {'pk': '__id__'}

        input_list = reverse('api:input-list')
        input_detail = reverse('api:input-detail', kwargs=placeholder_pk_kwargs)

        return {
            'content_type': 'application/json',
            'endpoints': {
                'input': {
                    'list': {'url': input_list, 'method': 'GET'},
                    'add': {'url': input_list, 'method': 'POST'},
                    'get': {'url': input_detail, 'method': 'GET'},
                },
            },
        }
