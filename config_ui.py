import argparse
import os
from flask import Flask, render_template, request, redirect

from pkg.configs.global_config import GlobalConfig


def create_app(project_name: str) -> Flask:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(repo_root, 'projects', project_name, 'templates')
    static_dir = os.path.join(repo_root, 'projects', project_name, 'static')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    config = GlobalConfig()
    config.initialize(project_name)

    @app.route('/')
    def index():
        return render_template('config.html', config=config.get_config())

    @app.route('/update', methods=['POST'])
    def update_config():
        updated = request.form.to_dict(flat=True)

        def try_cast_value(val):
            if val in ['True', 'true']:
                return True
            if val in ['False', 'false']:
                return False
            try:
                if '.' in val:
                    return float(val)
                return int(val)
            except Exception:
                return val

        def set_nested_value(cfg, key_path, value):
            parts = key_path.split('.')
            ref = cfg
            for part in parts[:-1]:
                if part.isdigit():
                    part = int(part)
                ref = ref[part]

            last_key = parts[-1]
            if last_key.isdigit() and isinstance(ref, list):
                ref[int(last_key)] = try_cast_value(value)
            else:
                ref[last_key] = try_cast_value(value)

        config_dict = config.get_config()
        for key_path, value in updated.items():
            set_nested_value(config_dict, key_path, value)

        config.save()
        config.reload()

        return redirect('/')

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description='Run configuration UI')
    parser.add_argument(
        '--project', default='frying_template', help='Project package name to run'
    )
    args = parser.parse_args()

    app = create_app(args.project)
    app.run(host='0.0.0.0', port=8000, debug=True)


if __name__ == '__main__':
    main()
