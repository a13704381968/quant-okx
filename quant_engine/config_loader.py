import os

class ConfigLoader:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {}
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            return
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    self.config[key.strip()] = value.strip()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def save_config(self, new_config):
        # Read original lines to preserve comments
        lines = []
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
        # Update existing keys
        updated_keys = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue
            
            if '=' in line:
                key = line.split('=', 1)[0].strip()
                if key in new_config:
                    new_lines.append(f"{key}={new_config[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Add new keys
        for key, value in new_config.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")
                
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        self.config.update(new_config)
