<<<<<<< HEAD
# Frying_FSM
FSM
=======
## FSM Template for SI Projects

This repository uses a multi-project layout with shared modules.

### Directory Structure
- `pkg/` - shared packages and configuration files
- `projects/` - individual project sources
- `scripts/` - project-specific run modules and utilities
- each project under `projects/` contains `static/` and `templates/` directories for web resources
    
### Dependencies
Install the required Python packages using the provided requirements file:
```bash
pip install -r requirements.txt
```

The `requirements.txt` file lists the following packages:
```text
protobuf==3.19.4
grpcio==1.34.1
grpcio-tools==1.34.1
psutil
graphviz
scipy~=1.7.3
numpy~=1.21.5
matplotlib
semver
pyyaml
py_trees
pyModbusTCP
neuromeka-clients
```

* Developer's Utils
```bash
sudo apt-get install -y screen \
&& sudo apt-get install -y jupyter
```

### How to Run
Use the common entry scripts located at the repository root.

* Run the main application
```bash
python3 run.py --project=frying_template
```

* Launch the configuration web UI
```bash
python3 config_ui.py --project=frying_template
```
>>>>>>> fc61e5e (chore: update .gitignore to exclude zip files and LOG folder)
