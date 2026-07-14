"""Install and uninstall AppLogs integrations."""

import subprocess
import os
from pathlib import Path


def install_integration(name, project_root):
    if name == 'all':
        chrome_rc = install_integration('chrome', project_root)
        shell_rc = install_integration('shell', project_root)
        return chrome_rc or shell_rc
    
    integration_dir = project_root / 'integrations' / name
    install_script = integration_dir / 'install.sh'
    
    if not install_script.exists():
        print(f'Error: Integration "{name}" not found at {integration_dir}')
        return 1
    
    os.chmod(install_script, 0o755)
    
    print(f'Installing {name} integration...')
    result = subprocess.run(['bash', str(install_script)], cwd=str(integration_dir))
    
    if result.returncode == 0:
        print(f'\n{name} integration installed successfully!')
    else:
        print(f'\nFailed to install {name} integration.')
    
    return result.returncode


def uninstall_integration(name):
    if name == 'all':
        uninstall_integration('shell')
        uninstall_integration('chrome')
        return 0
    
    if name == 'shell':
        config_dir = Path.home() / '.config' / 'applogs'
        shell_rc = _find_shell_rc()
        
        if shell_rc and shell_rc.exists():
            lines = shell_rc.read_text().splitlines()
            filtered = [l for l in lines if 'applogs.sh' not in l and 'AppLogs shell integration' not in l]
            shell_rc.write_text('\n'.join(filtered) + '\n')
            print(f'Removed AppLogs from {shell_rc}')
        
        if config_dir.exists():
            import shutil
            shutil.rmtree(config_dir)
            print(f'Removed {config_dir}')
        
        print('Shell integration uninstalled.')
        return 0
    
    if name == 'chrome':
        print('To uninstall Chrome extension:')
        print('  1. Open chrome://extensions/')
        print('  2. Find "AppLogs Chrome Collector"')
        print('  3. Click Remove')
        return 0
    
    print(f'Unknown integration: {name}')
    return 1


def _find_shell_rc():
    shell = os.environ.get('SHELL', '/bin/bash')
    shell_name = os.path.basename(shell)
    
    if 'zsh' in shell_name:
        return Path.home() / '.zshrc'
    elif 'bash' in shell_name:
        return Path.home() / '.bashrc'
    else:
        return Path.home() / '.profile'