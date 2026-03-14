from drf_spectacular.openapi import AutoSchema

class AppGroupAutoSchema(AutoSchema):
    """
    Custom AutoSchema that assigns tags to endpoints based on their app URL prefix
    so they are grouped correctly in Swagger UI.
    """
    def get_tags(self):
        path = self.path
        if path.startswith("/users/"):
            return ["users"]
        elif path.startswith("/api/content/"):
            return ["content"]
        elif path.startswith("/api/intelligence/"):
            return ["intelligence"]
        
        # Fallback to the default drf-spectacular tagging which tries to extract
        # the first path component after the prefix.
        return super().get_tags()
