"""
DynamoDB service for FabLink project.
Provides unified interface for DynamoDB operations in dev environment.
Complete MongoDB compatibility layer.
"""
import boto3
import json
import logging
import copy
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from django.conf import settings
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class DynamoDBService:
    """DynamoDB service class for handling document operations."""
    
    def __init__(self):
        """Initialize DynamoDB client and table reference."""
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        self.table_name = 'fablink-dynamodb-dev'
        self.table = self.dynamodb.Table(self.table_name)
        
    def create_document(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """Create a new document in DynamoDB."""
        try:
            data['id'] = doc_id
            data['created_at'] = datetime.utcnow().isoformat() + 'Z'
            data['updated_at'] = data['created_at']
            
            response = self.table.put_item(
                Item=data,
                ConditionExpression='attribute_not_exists(id)'
            )
            
            logger.info(f"Created document with id: {doc_id}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Document with id {doc_id} already exists")
                return False
            else:
                logger.error(f"Error creating document: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error creating document: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID from DynamoDB."""
        try:
            response = self.table.get_item(Key={'id': doc_id})
            item = response.get('Item')
            if item:
                logger.info(f"Retrieved document with id: {doc_id}")
                return dict(item)
            else:
                logger.info(f"Document not found with id: {doc_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
            return None
    
    def update_document(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """Update a document in DynamoDB."""
        try:
            # Remove id field from update data (it's the key)
            update_data = {k: v for k, v in data.items() if k != 'id'}
            update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            update_expression = "SET "
            expression_attribute_values = {}
            expression_attribute_names = {}
            
            for key, value in update_data.items():
                attr_name = f"#{key}"
                attr_value = f":{key}"
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                update_expression += f"{attr_name} = {attr_value}, "
            
            update_expression = update_expression.rstrip(', ')
            
            response = self.table.update_item(
                Key={'id': doc_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="UPDATED_NEW"
            )
            
            logger.info(f"Updated document with id: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {e}")
            return False
    
    def upsert_document(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """Upsert (insert or update) a document in DynamoDB."""
        try:
            current_time = datetime.utcnow().isoformat() + 'Z'
            data['id'] = doc_id
            data['updated_at'] = current_time
            
            existing = self.get_document(doc_id)
            if not existing:
                data['created_at'] = current_time
            
            response = self.table.put_item(Item=data)
            logger.info(f"Upserted document with id: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting document {doc_id}: {e}")
            return False
    
    def query_documents(self, filters: Dict[str, Any] = None, limit: int = None) -> List[Dict[str, Any]]:
        """Query documents with filters."""
        try:
            # Get all documents first (DynamoDB scan)
            scan_kwargs = {}
            if limit:
                scan_kwargs['Limit'] = limit
            
            response = self.table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            result = [dict(item) for item in items]
            
            # Apply filters in memory for complex queries
            if filters:
                result = self._apply_memory_filters(result, filters)
            
            logger.info(f"Queried {len(result)} documents")
            return result
            
        except Exception as e:
            logger.error(f"Error querying documents: {e}")
            return []
    
    def _apply_memory_filters(self, documents: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply filters in memory for complex MongoDB-style queries."""
        filtered = []
        
        for doc in documents:
            if self._document_matches_filter(doc, filters):
                filtered.append(doc)
        
        return filtered
    
    def _document_matches_filter(self, doc: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if document matches filter conditions."""
        if '$or' in filters:
            or_conditions = filters['$or']
            other_filters = {k: v for k, v in filters.items() if k != '$or'}
            
            # Check OR conditions
            or_match = False
            for condition in or_conditions:
                if self._document_matches_filter(doc, condition):
                    or_match = True
                    break
            
            if not or_match:
                return False
            
            # Check other conditions
            return self._document_matches_filter(doc, other_filters)
        
        # Check regular conditions
        for key, value in filters.items():
            if key.startswith('$'):
                continue
            
            if not self._field_matches_value(doc, key, value):
                return False
        
        return True
    
    def _field_matches_value(self, doc: Dict[str, Any], field_path: str, expected_value: Any) -> bool:
        """Check if nested field matches expected value."""
        if '.' not in field_path:
            return doc.get(field_path) == expected_value
        
        # Handle nested field like "steps.factory_list.factory_id"
        parts = field_path.split('.')
        current = doc
        
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                return False
            current = current[part]
            
            # If we hit an array, check if any item matches the remaining path
            if isinstance(current, list):
                remaining_path = '.'.join(parts[i+1:])
                for item in current:
                    if isinstance(item, dict) and self._field_matches_value(item, remaining_path, expected_value):
                        return True
                return False
        
        # Check final field
        final_field = parts[-1]
        if isinstance(current, list):
            # Check if any item in array has the field with expected value
            for item in current:
                if isinstance(item, dict) and item.get(final_field) == expected_value:
                    return True
            return False
        else:
            return current.get(final_field) == expected_value
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build DynamoDB filter expression from MongoDB-style filters."""
        if not filters:
            return {}
        
        if '$or' in filters:
            return self._handle_or_condition(filters)
        
        filter_expression = ""
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        for key, value in filters.items():
            if key.startswith('$'):
                continue
            
            # Handle nested field queries like "steps.factory_list.factory_id"
            if '.' in key:
                attr_name = f"#{key.replace('.', '_')}"
                attr_value = f":{key.replace('.', '_')}"
                
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                
                if filter_expression:
                    filter_expression += " AND "
                filter_expression += f"contains({attr_name}, {attr_value})"
            else:
                attr_name = f"#{key}"
                attr_value = f":{key}"
                
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                
                if filter_expression:
                    filter_expression += " AND "
                filter_expression += f"{attr_name} = {attr_value}"
        
        result = {}
        if filter_expression:
            result['FilterExpression'] = filter_expression
        if expression_attribute_names:
            result['ExpressionAttributeNames'] = expression_attribute_names
        if expression_attribute_values:
            result['ExpressionAttributeValues'] = expression_attribute_values
            
        return result
    
    def _handle_or_condition(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle $or conditions in filters."""
        or_conditions = filters.get('$or', [])
        other_filters = {k: v for k, v in filters.items() if k != '$or'}
        
        filter_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Handle OR conditions
        or_parts = []
        for i, condition in enumerate(or_conditions):
            for key, value in condition.items():
                attr_name = f"#or{i}_{key.replace('.', '_')}"
                attr_value = f":or{i}_{key.replace('.', '_')}"
                
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                
                # Handle nested field queries in OR conditions
                if '.' in key:
                    or_parts.append(f"contains({attr_name}, {attr_value})")
                else:
                    or_parts.append(f"{attr_name} = {attr_value}")
        
        if or_parts:
            filter_parts.append(f"({' OR '.join(or_parts)})")
        
        # Handle other conditions
        for key, value in other_filters.items():
            if key.startswith('$'):
                continue
                
            attr_name = f"#{key.replace('.', '_')}"
            attr_value = f":{key.replace('.', '_')}"
            
            expression_attribute_names[attr_name] = key
            expression_attribute_values[attr_value] = value
            
            if '.' in key:
                filter_parts.append(f"contains({attr_name}, {attr_value})")
            else:
                filter_parts.append(f"{attr_name} = {attr_value}")
        
        result = {}
        if filter_parts:
            result['FilterExpression'] = ' AND '.join(filter_parts)
        if expression_attribute_names:
            result['ExpressionAttributeNames'] = expression_attribute_names
        if expression_attribute_values:
            result['ExpressionAttributeValues'] = expression_attribute_values
            
        return result

# Global service instance
_dynamodb_service = None

def get_dynamodb_service():
    """Get or create DynamoDB service instance."""
    global _dynamodb_service
    if _dynamodb_service is None:
        _dynamodb_service = DynamoDBService()
    return _dynamodb_service

def ensure_indexes():
    """Ensure required indexes exist (no-op for DynamoDB)."""
    pass

def get_collection(collection_name: str):
    """MongoDB compatibility wrapper for DynamoDB."""
    service = get_dynamodb_service()
    
    class DynamoDBCursor:
        def __init__(self, results, projection=None):
            self.results = results
            self.projection = projection
            self._sort_key = None
            self._sort_direction = 1
            self._skip_count = 0
            self._limit_count = None
            
        def sort(self, key, direction=1):
            self._sort_key = key
            self._sort_direction = direction
            return self
            
        def skip(self, count):
            self._skip_count = count
            return self
            
        def limit(self, count):
            self._limit_count = count
            return self
            
        def __iter__(self):
            results = self.results[:]
            
            if self._sort_key:
                reverse = (self._sort_direction == -1)
                results.sort(key=lambda x: x.get(self._sort_key, ''), reverse=reverse)
            
            if self._skip_count:
                results = results[self._skip_count:]
            if self._limit_count:
                results = results[:self._limit_count]
                
            return iter(results)
            
        def __list__(self):
            return list(self.__iter__())
    
    class UpdateResult:
        def __init__(self, matched_count=0, modified_count=0):
            self.matched_count = matched_count
            self.modified_count = modified_count
    
    class DynamoDBCollectionWrapper:
        def __init__(self, service, collection_name):
            self.service = service
            self.collection_name = collection_name
        
        def find_one(self, query: Dict[str, Any], projection: Dict[str, int] = None) -> Optional[Dict[str, Any]]:
            """MongoDB compatible find_one with projection support."""
            if 'order_id' in query:
                doc_id = query['order_id']
                doc = self.service.get_document(doc_id)
            elif 'id' in query:
                doc = self.service.get_document(query['id'])
            else:
                results = self.service.query_documents(filters=query, limit=1)
                doc = results[0] if results else None
            
            if doc and projection:
                doc = self._apply_projection(doc, projection)
            
            return doc
        
        def find(self, query: Dict[str, Any] = None, projection: Dict[str, int] = None):
            """MongoDB compatible find with projection support."""
            results = self.service.query_documents(filters=query or {})
            
            if projection:
                results = [self._apply_projection(doc, projection) for doc in results]
                
            return DynamoDBCursor(results, projection)
        
        def count_documents(self, query: Dict[str, Any] = None) -> int:
            """MongoDB compatible count_documents method."""
            results = self.service.query_documents(filters=query or {})
            return len(results)
        
        def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False, array_filters: List[Dict] = None):
            """Complete MongoDB update_one compatibility."""
            if 'order_id' in query:
                doc_id = query['order_id']
            elif 'id' in query:
                doc_id = query['id']
            else:
                logger.error("Cannot update without order_id or id in query")
                return UpdateResult(0, 0)
            
            existing_doc = self.service.get_document(doc_id)
            
            if not existing_doc and not upsert:
                return UpdateResult(0, 0)
            
            if not existing_doc and upsert:
                new_doc = {}
                if '$setOnInsert' in update:
                    new_doc.update(update['$setOnInsert'])
                if '$set' in update:
                    new_doc.update(update['$set'])
                
                success = self.service.upsert_document(doc_id, new_doc)
                return UpdateResult(1 if success else 0, 1 if success else 0)
            
            modified_doc = copy.deepcopy(existing_doc)
            modified = False
            
            if '$set' in update:
                modified = self._apply_set_operation(modified_doc, update['$set']) or modified
            
            if '$pull' in update:
                modified = self._apply_pull_operation(modified_doc, update['$pull'], array_filters) or modified
            
            if '$push' in update:
                modified = self._apply_push_operation(modified_doc, update['$push'], array_filters) or modified
            
            if modified:
                success = self.service.update_document(doc_id, modified_doc)
                return UpdateResult(1 if success else 0, 1 if success else 0)
            
            return UpdateResult(1, 0)
        
        def _apply_projection(self, doc: Dict[str, Any], projection: Dict[str, int]) -> Dict[str, Any]:
            """Apply MongoDB-style projection to document."""
            if not projection:
                return doc
            
            result = copy.deepcopy(doc)
            
            if projection.get('_id') == 0:
                result = {k: v for k, v in result.items() if k != '_id'}
            
            # Include only specified fields (if any positive projections)
            include_fields = {k for k, v in projection.items() if v == 1}
            if include_fields:
                result = {k: v for k, v in result.items() if k in include_fields}
            
            return result
        
        def _apply_set_operation(self, doc: Dict[str, Any], set_data: Dict[str, Any]) -> bool:
            """Apply $set operation to document."""
            modified = False
            for key, value in set_data.items():
                if self._set_nested_value(doc, key, value):
                    modified = True
            return modified
        
        def _apply_pull_operation(self, doc: Dict[str, Any], pull_data: Dict[str, Any], array_filters: List[Dict] = None) -> bool:
            """Apply $pull operation to document."""
            modified = False
            for path, condition in pull_data.items():
                if self._pull_from_array(doc, path, condition, array_filters):
                    modified = True
            return modified
        
        def _apply_push_operation(self, doc: Dict[str, Any], push_data: Dict[str, Any], array_filters: List[Dict] = None) -> bool:
            """Apply $push operation to document."""
            modified = False
            for path, value in push_data.items():
                if self._push_to_array(doc, path, value, array_filters):
                    modified = True
            return modified
        
        def _set_nested_value(self, doc: Dict[str, Any], path: str, value: Any) -> bool:
            """Set nested value in document."""
            keys = path.split('.')
            current = doc
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            final_key = keys[-1]
            if current.get(final_key) != value:
                current[final_key] = value
                return True
            return False
        
        def _pull_from_array(self, doc: Dict[str, Any], path: str, condition: Dict[str, Any], array_filters: List[Dict] = None) -> bool:
            """Pull items from array based on condition."""
            if '$[' in path:
                return self._handle_array_filter_pull(doc, path, condition, array_filters)
            
            keys = path.split('.')
            current = doc
            
            for key in keys[:-1]:
                if key not in current:
                    return False
                current = current[key]
            
            array_key = keys[-1]
            if array_key not in current or not isinstance(current[array_key], list):
                return False
            
            original_length = len(current[array_key])
            current[array_key] = [item for item in current[array_key] if not self._matches_condition(item, condition)]
            
            return len(current[array_key]) != original_length
        
        def _push_to_array(self, doc: Dict[str, Any], path: str, value: Any, array_filters: List[Dict] = None) -> bool:
            """Push item to array."""
            if '$[' in path:
                return self._handle_array_filter_push(doc, path, value, array_filters)
            
            keys = path.split('.')
            current = doc
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            array_key = keys[-1]
            if array_key not in current:
                current[array_key] = []
            elif not isinstance(current[array_key], list):
                return False
            
            current[array_key].append(value)
            return True
        
        def _handle_array_filter_pull(self, doc: Dict[str, Any], path: str, condition: Dict[str, Any], array_filters: List[Dict] = None) -> bool:
            """Handle array filter pull operations."""
            # Parse path like "steps.$[step].factory_list"
            parts = path.split('.')
            if len(parts) < 3:
                return False
            
            array_field = parts[0]  # "steps"
            filter_placeholder = parts[1]  # "$[step]"
            target_field = parts[2]  # "factory_list"
            
            if array_field not in doc or not isinstance(doc[array_field], list):
                return False
            
            # Extract filter name from placeholder
            filter_name = filter_placeholder[2:-1]  # "step"
            filter_condition = None
            if array_filters:
                for af in array_filters:
                    # Handle both formats: {'step.index': 1} and {'step': {'index': 1}}
                    if f'{filter_name}.index' in af:
                        filter_condition = {'index': af[f'{filter_name}.index']}
                        break
                    elif filter_name in af:
                        filter_condition = af[filter_name]
                        break
            
            if not filter_condition:
                return False
            
            modified = False
            for item in doc[array_field]:
                if self._matches_condition(item, filter_condition):
                    if target_field in item and isinstance(item[target_field], list):
                        original_length = len(item[target_field])
                        item[target_field] = [sub_item for sub_item in item[target_field] 
                                            if not self._matches_condition(sub_item, condition)]
                        if len(item[target_field]) != original_length:
                            modified = True
            
            return modified
        
        def _handle_array_filter_push(self, doc: Dict[str, Any], path: str, value: Any, array_filters: List[Dict] = None) -> bool:
            """Handle array filter push operations."""
            # Parse path like "steps.$[step].factory_list"
            parts = path.split('.')
            if len(parts) < 3:
                return False
            
            array_field = parts[0]  # "steps"
            filter_placeholder = parts[1]  # "$[step]"
            target_field = parts[2]  # "factory_list"
            
            if array_field not in doc or not isinstance(doc[array_field], list):
                return False
            
            # Extract filter name from placeholder
            filter_name = filter_placeholder[2:-1]  # "step"
            filter_condition = None
            if array_filters:
                for af in array_filters:
                    # Handle both formats: {'step.index': 1} and {'step': {'index': 1}}
                    if f'{filter_name}.index' in af:
                        filter_condition = {'index': af[f'{filter_name}.index']}
                        break
                    elif filter_name in af:
                        filter_condition = af[filter_name]
                        break
            
            if not filter_condition:
                return False
            
            modified = False
            for item in doc[array_field]:
                if self._matches_condition(item, filter_condition):
                    if target_field not in item:
                        item[target_field] = []
                    elif not isinstance(item[target_field], list):
                        continue
                    
                    item[target_field].append(value)
                    modified = True
            
            return modified
        
        def _matches_condition(self, item: Dict[str, Any], condition: Dict[str, Any]) -> bool:
            """Check if item matches condition."""
            if not isinstance(item, dict) or not isinstance(condition, dict):
                return item == condition
            
            for key, value in condition.items():
                if key == '$or':
                    if not any(self._matches_condition(item, sub_cond) for sub_cond in value):
                        return False
                elif key not in item or item[key] != value:
                    return False
            
            return True
    
    return DynamoDBCollectionWrapper(service, collection_name)
