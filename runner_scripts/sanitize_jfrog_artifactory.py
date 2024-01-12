from pyartifactory import Artifactory

ARTIFACTORY_BASE_URL = "https://cura.jfrog.io/artifactory"
USERNAME = "YOUR-ID"
PASSWORD = "YOUR-PASSWORD"

def initialize_artifactory():
    return Artifactory(url=ARTIFACTORY_BASE_URL, auth=(USERNAME, PASSWORD))

ARTIFACT_PATHS = {"cura-conan-dev-local/ultimaker/curaengine"          : True,
                  "cura-conan-dev-local/ultimaker/cura"                : True,
                  "cura-conan-dev-local/ultimaker/fdm_printer"         : True,
                  "cura-conan-dev-local/ultimaker/uranium"             : True,
                  "cura-conan-dev-local/_/curaengine"                  : True,
                  "cura-conan-dev-local/_/cura"                        : True,
                  "cura-conan-dev-local/_/fdm_printer"                 : True,
                  "cura-conan-dev-local/_/uranium"                     : True,
                  "cura-conan-cci-remote-cache/ultimaker/curaengine"   : True,
                  "cura-conan-cci-remote-cache/ultimaker/cura"         : True,
                  "cura-conan-cci-remote-cache/ultimaker/fdm_printer"  : True,
                  "cura-conan-cci-remote-cache/ultimaker/uranium"      : True,
                  "cura-conan-cci-remote-cache/_/curaengine"           : True,
                  "cura-conan-cci-remote-cache/_/cura"                 : True,
                  "cura-conan-cci-remote-cache/_/fdm_printer"          : True,
                  "cura-conan-cci-remote-cache/_/uranium"              : True,
                  "cura_conan-cci-remote-cache"						             : False}


def list_artifacts(artifactory_client, artifact_path, depth):
    return artifactory_client.artifacts.list(f"{artifact_path}/", depth)


def delete_artifact(artifactory_client, artifact_path):
    artifactory_client.artifacts.delete(artifact_path)


def artifact_modified_by_anonymous(artifactory_client, artifact_path):
    return str(artifactory_client.artifacts.info(artifact_path).createdBy) == "anonymous"


def process_artifact(artifactory_client, artifact_path, sequence_nr, file):
    artifact_file_path = f"{artifact_path}{file.uri}"

    if artifact_modified_by_anonymous(artifactory_client, artifact_file_path):
        sequence_nr += 1
        print(f"{sequence_nr}: {artifact_file_path}")
        delete_artifact(artifactory_client, artifact_file_path)
        return sequence_nr

    if ARTIFACT_PATHS[artifact_path]:
        artifact_files = list_artifacts(artifactory_client, artifact_file_path, depth=2).files
        for ar in artifact_files:
            ar_path = f"{artifact_file_path}{ar.uri}"
            if artifact_modified_by_anonymous(artifactory_client, ar_path):
                sequence_nr += 1
                print(f"{sequence_nr}: {ar_path}")
                delete_artifact(artifactory_client, ar_path)

    return sequence_nr


def main():
    artifactory_client = initialize_artifactory()

    for artifact_path in ARTIFACT_PATHS:
        artifacts = list_artifacts(artifactory_client, artifact_path, depth=1).files

        number_files_deleted = 0
        for file in artifacts:
            number_files_deleted = process_artifact(artifactory_client, artifact_path, number_files_deleted, file)


if __name__ == "__main__":
    main()
