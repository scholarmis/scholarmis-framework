import json

class JsonObject:
    def __init__(self, dictionary):
        # Recursively convert dictionaries and lists into JsonObject instances
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.__dict__[key] = JsonObject(value)
            elif isinstance(value, list):
                self.__dict__[key] = [JsonObject(item) if isinstance(item, dict) else item for item in value]
            else:
                self.__dict__[key] = value

    def __getattr__(self, name):
        # Return the value if it exists, otherwise raise an AttributeError
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name, value):
        # Allow setting new attributes dynamically
        self.__dict__[name] = value
    
    def to_dict(self):
        # Recursively convert JsonObject instances back to dictionaries
        def convert(obj):
            if isinstance(obj, JsonObject):
                return {k: convert(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            else:
                return obj

        return convert(self)
    
    def to_json(self):
        # Serialize the object to a JSON string
        return json.dumps(self.to_dict())
    

def to_json(obj):
    # Convert any object to a dictionary and return a JsonObject instance
    if isinstance(obj, dict):
        return JsonObject(obj).to_json()
    else:
        return JsonObject(obj.__dict__)


def from_json(json_str):
    # Deserialize a JSON string into a JsonObject
    return JsonObject(json.loads(json_str)).to_dict()
