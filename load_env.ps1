if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        # Clean up whitespace
        $line = $_.Trim()
        
        # Skip empty lines and comments
        if ($line -and -not $line.StartsWith('#')) {
            # Split into key and value at the first '='
            $key, $value = $line -split '=', 2
            
            if ($key) {
                # Trim spaces and strip surrounding quotes from the value
                $cleanKey = $key.Trim()
                $cleanValue = $value.Trim() -replace "^['`"]|['`"]$"
                
                # Set the environment variable for the current session
                Set-Item "Env:\$cleanKey" $cleanValue
            }
        }
    }
    Write-Host "Successfully loaded .env file into environment variables." -ForegroundColor Green
} else {
    Write-Warning ".env file not found in the current directory."
}
