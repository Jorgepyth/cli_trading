import os
import hashlib
from getpass import getpass
from dotenv import load_dotenv

def local_auth():
    """
    Checks if a local developer passphrase is provided correctly 
    per Protocol 0 (Zero-Trust).
    In a real scenario, the hash should be stored in .env.
    """
    load_dotenv()
    
    # Normally, dev creates this hash manually and adds to .env
    # e.g. python -c "import hashlib, binascii; salt=b'blast_cli_salt'; key = hashlib.pbkdf2_hmac('sha256', 'mypass'.encode(), salt, 100000); print(binascii.hexlify(key).decode())"
    expected_hash = os.getenv("BLAST_DEV_PASSPHRASE_HASH")
    
    # If not set, let's allow it but warn, or we can strictly deny. Let's deny to be strict.
    if not expected_hash:
        print("ERROR: BLAST_DEV_PASSPHRASE_HASH not set in .env")
        return False
        
    password = getpass("Developer Passphrase: ")
    
    salt_str = os.getenv("BLAST_CLI_SALT")
    if not salt_str:
        print("[bold red]CRITICAL SECURITY FAULT: BLAST_CLI_SALT not defined in .env. Halting to preserve Zero-Trust.[/bold red]")
        raise ValueError("BLAST_CLI_SALT missing. Cannot generate entropy.")
    salt = salt_str.encode('utf-8')
    
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    import binascii
    hashed_input = binascii.hexlify(key).decode('utf-8')
    
    # For backwards compatibility during transition, check if the expected hash is a legacy weak sha256
    # A standard sha256 hex digest is 64 chars. We will allow transition.
    if len(expected_hash) == 64 and expected_hash == hashlib.sha256(password.encode()).hexdigest():
        print("[WARNING] You are using an outdated legacy SHA-256 hash. Please update .env to use PBKDF2.")
        return True
    
    return hashed_input == expected_hash
