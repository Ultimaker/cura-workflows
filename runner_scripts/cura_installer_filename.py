import os

enterprise = "-Enterprise" if "${{ inputs.enterprise }}" == "true" else ""
installer_filename = f"UltiMaker-Cura-{os.getenv('CURA_VERSION_FULL')}{enterprise}-linux-${{ inputs.architecture }}"
output_env = os.environ["GITHUB_OUTPUT"]
content = ""
if os.path.exists(output_env):
    with open(output_env, "r") as f:
        content = f.read()
with open(output_env, "w") as f:
    f.write(content)
    f.writelines(f"INSTALLER_FILENAME={installer_filename}\n")
