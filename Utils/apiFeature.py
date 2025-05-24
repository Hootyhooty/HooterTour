from copy import deepcopy
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIFeatures:
    def __init__(self, query, query_params):
        self.query = query  # MongoEngine QuerySet
        self.query_params = query_params  # flask.request.args.to_dict()

    def filter(self):
        query_obj = deepcopy(self.query_params)
        excluded_fields = ['page', 'sort', 'limit', 'fields']
        for field in excluded_fields:
            query_obj.pop(field, None)

        # Convert query params to MongoEngine filter kwargs
        filter_kwargs = {}
        for key, value in query_obj.items():
            # Handle operators like gte, lte, gt, lt
            if key.endswith('[gte]'):
                filter_kwargs[key[:-5] + '__gte'] = value
            elif key.endswith('[lte]'):
                filter_kwargs[key[:-5] + '__lte'] = value
            elif key.endswith('[gt]'):
                filter_kwargs[key[:-5] + '__gt'] = value
            elif key.endswith('[lt]'):
                filter_kwargs[key[:-5] + '__lt'] = value
            else:
                filter_kwargs[key] = value

        # Apply filters to MongoEngine QuerySet
        self.query = self.query.filter(**filter_kwargs)
        logger.debug(f"Filtered query: {query_obj}")
        return self

    def sort(self):
        if 'sort' in self.query_params:
            sort_by = self.query_params['sort'].replace(',', ' ')
            # MongoEngine sort syntax: +field for ascending, -field for descending
            sort_fields = []
            for field in sort_by.split():
                if field.startswith('-'):
                    sort_fields.append(f'-{field[1:]}')
                else:
                    sort_fields.append(f'+{field}')
            self.query = self.query.order_by(*sort_fields)
        else:
            self.query = self.query.order_by('-created_at')  # Default: descending by created_at
        logger.debug(f"Sort applied: {self.query_params.get('sort', '-created_at')}")
        return self

    def limit_fields(self):
        if 'fields' in self.query_params:
            fields = self.query_params['fields'].replace(',', ' ').split()
            # Remove empty strings and validate fields
            fields = [f for f in fields if f]
            if fields:
                # Validate fields against model schema
                valid_fields = []
                for field in fields:
                    try:
                        self.query._document._lookup_field(field.split('.'))
                        valid_fields.append(field)
                    except Exception as e:
                        logger.warning(f"Invalid field ignored: {field} ({str(e)})")
                if valid_fields:
                    self.query = self.query.only(*valid_fields)
                else:
                    logger.debug("No valid fields to limit")
        logger.debug(f"Fields limited: {self.query_params.get('fields', 'all')}")
        return self

    def paginate(self):
        page = int(self.query_params.get('page', 1))
        limit = int(self.query_params.get('limit', 100))
        skip = (page - 1) * limit
        self.query = self.query.skip(skip).limit(limit)
        logger.debug(f"Paginated: page={page}, limit={limit}")
        return self