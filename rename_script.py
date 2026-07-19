import os

extensions = {'.py', '.md', '.txt', '.yaml', '.toml', '.example', '.env', '.json', '.ts', '.tsx', '.html', '.css'}
exclude_dirs = {'.git', 'venv', '.venv', '__pycache__', 'node_modules', '.streamlit', '.pytest_cache', 'dist', 'build'}

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Order matters: replace longer strings first
        replacements = [
            ("care-india", "care-india"),
            ("care-india", "care-india"),
            ("care-india", "care-india"),
            ("care-india", "care-india"),
            ("care_india_agent", "care_india_agent"),
            ("care-india-api", "care-india-api"),
            ("care-india", "care-india"),
            ("CARE_INDIA", "CARE_INDIA")
        ]
        
        new_content = content
        for old, new in replacements:
            new_content = new_content.replace(old, new)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {filepath}")
    except Exception as e:
        pass

for root, dirs, files in os.walk('.'):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if any(file.endswith(ext) for ext in extensions) or file in ['Makefile', 'Dockerfile']:
            replace_in_file(os.path.join(root, file))

print("Project successfully renamed to care-india across all files!")
