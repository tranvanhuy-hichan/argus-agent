const dict: Record<string, string> = {
  'Mã hóa khóa bí mật': 'Secrets encryption',
  'API key, token Telegram và biến môi trường của MCP được mã hóa trong config.json.': 'API keys, Telegram tokens and MCP environment values are encrypted in config.json.',
  'Khóa đã mã hóa': 'Encrypted secrets',
  'Khóa còn chữ thường': 'Plaintext secrets',
  'Nơi giữ khóa chủ': 'Master key location',
  'biến môi trường ARGUS_MASTER_KEY': 'ARGUS_MASTER_KEY environment variable',
  'keychain của hệ điều hành': 'OS keychain',
  'chưa có': 'none yet',
  'Mã hóa đã tắt (ARGUS_ENCRYPT=0).': 'Encryption is turned off (ARGUS_ENCRYPT=0).',
  '{n} khóa không giải mã được (mất hoặc sai khóa chủ). Hãy nhập lại trong giao diện hoặc khôi phục khóa chủ.': '{n} secret(s) cannot be decrypted (master key lost or wrong). Re-enter them in the UI or restore the master key.',
  'Còn khóa chưa mã hóa. Chạy: argus secrets encrypt': 'Some secrets are not encrypted. Run: argus secrets encrypt',
  'Hãy sao lưu khóa chủ (argus backup --include-key --encrypt): mất nó thì không giải mã lại được các khóa.': 'Back up the master key (argus backup --include-key --encrypt): without it the secrets cannot be decrypted.',
}

export default dict
