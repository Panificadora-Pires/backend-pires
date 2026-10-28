from rest_framework import pagination
from rest_framework.response import Response


class CustomPagination(pagination.PageNumberPagination):
    page_size = 10  # tamanho padrão da página
    page_size_query_param = 'page_size'  # permitir mudar via query parameter
    max_page_size = 100  # tamanho máximo da página que pode ser solicitado

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.page.paginator.per_page,
            'total_pages': self.page.paginator.num_pages,
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'required': ['count', 'page', 'page_size', 'total_pages', 'results'],
            'properties': {
                'count': {'type': 'integer', 'example': 123},
                'next': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'previous': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'page': {'type': 'integer', 'example': 1},
                'page_size': {'type': 'integer', 'example': 10},
                'total_pages': {'type': 'integer', 'example': 13},
                'results': schema,
            },
        }
