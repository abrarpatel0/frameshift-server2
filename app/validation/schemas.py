"""
Validation schemas - DEPRECATED: Use @validate_json decorator instead.

Note: These schemas are not currently used while routes validate via
the @validate_json() decorator (see app.utils.decorators).

To use Marshmallow schemas, update routes like:
    from marshmallow import ValidationError
    schema = RegisterSchema()
    try:
        data = schema.load(request.get_json())
    except ValidationError as err:
        return error_response(str(err.messages), 400)
"""
from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    """Schema for user registration."""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    full_name = fields.String(validate=validate.Length(max=255))


class LoginSchema(Schema):
    """Schema for user login."""
    email = fields.Email(required=True)
    password = fields.String(required=True)


class VerifyEmailSchema(Schema):
    """Schema for email verification."""
    token = fields.String(required=True)


class ForgotPasswordSchema(Schema):
    """Schema for forgot password."""
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    """Schema for password reset."""
    token = fields.String(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))


class ChangePasswordSchema(Schema):
    """Schema for changing password."""
    currentPassword = fields.String(required=True)
    newPassword = fields.String(required=True, validate=validate.Length(min=8))
