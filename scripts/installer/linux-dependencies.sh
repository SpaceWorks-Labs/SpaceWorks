#!/usr/bin/env bash
install_linux_dependencies() {
  local runner_packages=()
  [[ "${INSTALL_RUNNER:-N}" =~ ^[Yy] ]] && runner_packages=(python3)
  case "$PACKAGE_FAMILY" in
    apt)
      ${SUDO[@]+"${SUDO[@]}"} apt-get update
      ${SUDO[@]+"${SUDO[@]}"} env DEBIAN_FRONTEND=noninteractive apt-get install -y curl tar util-linux ${runner_packages[@]+"${runner_packages[@]}"}
      [[ "$MISSING_DOCKER" == 0 ]] \
        || ${SUDO[@]+"${SUDO[@]}"} env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
      if [[ "$MISSING_COMPOSE" == 1 ]]; then
        ${SUDO[@]+"${SUDO[@]}"} env DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-v2 \
          || ${SUDO[@]+"${SUDO[@]}"} env DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-plugin \
          || true
      fi
      ;;
    dnf)
      manager=dnf; command -v dnf >/dev/null 2>&1 || manager=yum
      ${SUDO[@]+"${SUDO[@]}"} "$manager" install -y curl tar util-linux ${runner_packages[@]+"${runner_packages[@]}"}
      if [[ "$MISSING_DOCKER" == 1 ]]; then
        repo_os=centos
        [[ "${ID:-}" == fedora ]] && repo_os=fedora
        [[ "${ID:-}" == rhel ]] && repo_os=rhel
        if [[ "$manager" == dnf ]]; then
          ${SUDO[@]+"${SUDO[@]}"} dnf install -y dnf-plugins-core
          ${SUDO[@]+"${SUDO[@]}"} dnf config-manager --add-repo "https://download.docker.com/linux/$repo_os/docker-ce.repo" \
            || ${SUDO[@]+"${SUDO[@]}"} dnf config-manager addrepo --from-repofile="https://download.docker.com/linux/$repo_os/docker-ce.repo"
        else
          ${SUDO[@]+"${SUDO[@]}"} yum install -y yum-utils
          ${SUDO[@]+"${SUDO[@]}"} yum-config-manager --add-repo "https://download.docker.com/linux/$repo_os/docker-ce.repo"
        fi
        ${SUDO[@]+"${SUDO[@]}"} "$manager" install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      else
        ${SUDO[@]+"${SUDO[@]}"} "$manager" install -y docker-compose-plugin || true
      fi
      ;;
    pacman) ${SUDO[@]+"${SUDO[@]}"} pacman -Syu --noconfirm --needed curl tar util-linux docker docker-compose ${runner_packages[@]+"${runner_packages[@]}"} ;;
    zypper) ${SUDO[@]+"${SUDO[@]}"} zypper --non-interactive install curl tar util-linux docker docker-compose ${runner_packages[@]+"${runner_packages[@]}"} ;;
  esac
}
