"""
Example usage of the error_tracker module.

This file demonstrates different ways to use the error tracking functionality.
"""

from .error_tracker import track_errors, handle_errors, log_error

# Example 1: Using the track_errors decorator
@track_errors
def process_user_data(username, email, data):
    """
    Example function that demonstrates error tracking.
    
    This function will log errors with context about the function arguments.
    The error will still be raised after logging.
    """
    if not username:
        raise ValueError("Username cannot be empty")
        
    # Process user data...
    result = data['key']  # Will raise KeyError if 'key' doesn't exist
    
    return f"Processed data for {username}"

# Example 2: Using track_errors with options
@track_errors(with_context=False, module_name="user_processor")
def validate_user_input(username, password):
    """
    Example function with track_errors and custom options.
    
    This demonstrates error tracking without including argument values
    and with a custom module name for the logger.
    """
    if len(password) < 8:
        raise ValueError("Password is too short")
    
    return True

# Example 3: Using handle_errors to catch and return default
@handle_errors(default_return=False)
def is_user_active(username):
    """
    Example function with error handling.
    
    This function will log errors and return False instead of raising exceptions.
    """
    if not username:
        raise ValueError("Username cannot be empty")
    
    # Check if user is active...
    if username == "test_inactive":
        return False
    
    return True

# Example 4: Direct error logging
def api_request_handler(request_data):
    """
    Example function that manually logs errors.
    """
    try:
        # Process API request...
        if 'user' not in request_data:
            raise KeyError("Missing required 'user' field")
        
        # More processing...
        return {"status": "success"}
    
    except Exception as e:
        # Manually log the error with context
        log_error(
            error=e,
            context={"request_data": str(request_data)},
            user_info={"username": request_data.get("user"), "ip": "127.0.0.1"},
            module_name="api.handler"
        )
        # Re-raise or handle the error...
        raise

# Example of how these might be used in your code
if __name__ == "__main__":
    # This will log an error with function arguments and raise the exception
    try:
        process_user_data("john", "john@example.com", {"wrong_key": "value"})
    except KeyError as e:
        print(f"Caught expected error: {e}")
    
    # This will log an error with a custom module name and raise the exception
    try:
        validate_user_input("john", "123")
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    # This will log an error but return False instead of raising
    result = is_user_active("")
    print(f"Result of is_user_active: {result}")  # Will print False
    
    # This will manually log an error and raise
    try:
        api_request_handler({"data": "some data"})
    except KeyError as e:
        print(f"Caught expected error: {e}") 