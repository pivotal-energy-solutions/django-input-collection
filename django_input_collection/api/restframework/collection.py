from django.urls import reverse

from ...collection import BaseAPICollector, BaseAPISpecification


class RestFrameworkSpecification(BaseAPISpecification):
    content_type = 'application/json'

    def get_api_info(self):
        info = super(RestFrameworkSpecification, self).get_api_info()

        input_list = reverse('api:input-list')
        input_detail = reverse('api:input-detail', kwargs={'pk': '__id__'})

        info['endpoints'] = {
            'input': {
                'list': {'url': input_list, 'method': 'GET'},
                'add': {'url': input_list, 'method': 'POST'},
                'get': {'url': input_detail, 'method': 'GET'},
            },
        }
        return info


class RestFrameworkCollector(BaseAPICollector):
    specification_class = RestFrameworkSpecification
