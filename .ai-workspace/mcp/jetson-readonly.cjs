#!/usr/bin/env node
'use strict';

const { spawn } = require('node:child_process');

const host = process.env.JETSON_SSH_HOST || '116.148.216.66';
const port = process.env.JETSON_SSH_PORT || '30046';
const user = process.env.JETSON_SSH_USER || 'root';
const target = `${user}@${host}`;
const identityFile = process.env.JETSON_SSH_IDENTITY || 'C:/Users/kun/.ssh/id_rsa';
const knownHostsFile = process.env.JETSON_SSH_KNOWN_HOSTS || 'C:/Users/kun/.ssh/known_hosts';
const allowedContainers = new Set((process.env.JETSON_READONLY_CONTAINERS || 'core,firmware-sensors,scout-nav,scout-nav-pre-dual-20260819,ota_web,kn_nav_container,d360_navigation_container').split(',').map((x) => x.trim()).filter(Boolean));
const workspaces = {
  ros1: '/home/jetson/Scout_mini_navigation',
  ros2: '/home/jetson/kn_nav',
  external_3d: '/home/jetson/docker_ws_backup',
};

const operation = process.argv[2] || 'help';
const arg1 = process.argv[3];
const arg2 = process.argv[4];

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(2);
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'"'"'`)}'`;
}

function commandForOperation() {
  switch (operation) {
    case 'help':
      process.stdout.write([
        'Allowed read-only operations:',
        '  identity',
        '  uptime',
        '  disk',
        '  ports',
        '  docker-ps',
        '  docker-logs <container> [tail<=1000]',
        '  git-status <ros1|ros2|external_3d>',
        '  ros1-nodes',
        '  ros2-nodes',
      ].join('\n') + '\n');
      process.exit(0);
      break;
    case 'identity':
      return "printf '%s\\n' '--- uname ---'; uname -a; printf '%s\\n' '--- os-release ---'; sed -n '1,12p' /etc/os-release";
    case 'uptime':
      return "uptime; printf '%s\\n' '--- memory ---'; free -h";
    case 'disk':
      return 'df -h';
    case 'ports':
      return 'ss -lntup';
    case 'docker-ps':
      return "docker ps --no-trunc --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'";
    case 'docker-logs': {
      if (!allowedContainers.has(arg1)) fail(`Container is not allowlisted: ${arg1 || '<missing>'}`);
      const requestedTail = Number.parseInt(arg2 || '200', 10);
      const tail = Number.isFinite(requestedTail) ? Math.min(Math.max(requestedTail, 1), 1000) : 200;
      return `docker logs --timestamps --tail ${tail} ${shellQuote(arg1)}`;
    }
    case 'git-status': {
      const workspace = workspaces[arg1];
      if (!workspace) fail(`Unknown workspace: ${arg1 || '<missing>'}`);
      return `git -C ${shellQuote(workspace)} status --short --branch && git -C ${shellQuote(workspace)} diff --stat`;
    }
    case 'ros1-nodes':
      return "bash -lc 'source /opt/ros/noetic/setup.bash && rosnode list'";
    case 'ros2-nodes':
      return "docker exec kn_nav_container bash -lc 'source /opt/ros/humble/setup.bash && ros2 node list'";
    default:
      fail(`Operation is not allowed: ${operation}`);
  }
}

const remoteCommand = commandForOperation();
const sshArgs = [
  '-F', 'NUL',
  '-i', identityFile,
  '-o', `UserKnownHostsFile=${knownHostsFile}`,
  '-o', 'StrictHostKeyChecking=yes',
  '-o', 'BatchMode=yes',
  '-o', 'ConnectTimeout=10',
  '-o', 'ServerAliveInterval=15',
  '-o', 'ServerAliveCountMax=2',
  '-p', String(port),
  target,
  remoteCommand,
];
const child = spawn('ssh', sshArgs, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let outputBytes = 0;
const maxOutputBytes = 2 * 1024 * 1024;

function forward(stream, destination) {
  stream.on('data', (chunk) => {
    outputBytes += chunk.length;
    if (outputBytes > maxOutputBytes) {
      child.kill();
      destination.write('\nOutput exceeded 2 MiB and was terminated.\n');
      return;
    }
    destination.write(chunk);
  });
}

forward(child.stdout, process.stdout);
forward(child.stderr, process.stderr);
child.on('error', (error) => fail(`Failed to start ssh: ${error.message}`));
child.on('close', (code) => process.exit(code ?? 1));
