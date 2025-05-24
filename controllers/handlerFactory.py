from flask import request
from Utils.AppError import AppError
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger('mongoengine').setLevel(logging.DEBUG)

class APIFeatures:
    def __init__(self, query, query_string):
        self.query = query
        self.query_string = query_string

    def filter(self):
        query_obj = {**self.query_string}
        excluded_fields = ['page', 'sort', 'limit', 'fields']
        for field in excluded_fields:
            query_obj.pop(field, None)

        for key, value in query_obj.items():
            if isinstance(value, str) and ',' in value:
                query_obj[key] = {'$in': value.split(',')}
            elif isinstance(value, str) and value.startswith('['):
                import json
                query_obj[key] = json.loads(value)

        query_str = str(query_obj).replace("'", '"').replace('gte', '$gte').replace('gt', '$gt').replace('lte', '$lte').replace('lt', '$lt')
        import json
        query_obj = json.loads(query_str)

        self.query = self.query.filter(__raw__=query_obj)
        return self

    def sort(self):
        if 'sort' in self.query_string:
            sort_by = self.query_string['sort'].split(',')
            sort_dict = {}
            for field in sort_by:
                if field.startswith('-'):
                    sort_dict[field[1:]] = -1
                else:
                    sort_dict[field] = 1
            self.query = self.query.order_by(*[f"{'' if order == 1 else '-'}{field}" for field, order in sort_dict.items()])
        else:
            self.query = self.query.order_by('-createdAt')
        return self

    def limit_fields(self):
        if 'fields' in self.query_string:
            fields = self.query_string['fields'].split(',')
            self.query = self.query.only(*fields)
        return self

    def paginate(self):
        page = int(self.query_string.get('page', 1))
        limit = int(self.query_string.get('limit', 100))
        skip = (page - 1) * limit
        self.query = self.query.skip(skip).limit(limit)
        return self