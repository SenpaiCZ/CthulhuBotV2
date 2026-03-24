// Initialize the Discord Embedded App SDK
const discordSdk = new DiscordSDK.DiscordSDK(ACTIVITY_CLIENT_ID);

/**
 * Setup the Discord Activity.
 * This is called after the DOM is ready.
 */
async function setup() {
    try {
        console.log('Initializing Discord SDK...');
        await discordSdk.ready();
        console.log('Discord SDK is ready.');

        // Authenticate with Discord
        console.log('Authenticating...');
        const auth = await authenticate();
        console.log('Authenticated successfully:', auth);

        document.getElementById('status').innerText = `Welcome, ${auth.user.username}!`;
        document.getElementById('loading').style.display = 'none';
        document.getElementById('activity-content').style.display = 'block';

    } catch (error) {
        console.error('Error during Discord Activity initialization:', error);
        document.getElementById('status').innerText = 'Error initializing activity. Please check the console.';
    }
}

/**
 * Perform OAuth2 authentication with Discord.
 */
async function authenticate() {
    // 1. Request an access token from Discord
    const { code } = await discordSdk.commands.authorize({
        client_id: ACTIVITY_CLIENT_ID,
        response_type: 'code',
        state: '',
        prompt: 'none',
        scope: ['identify', 'guilds'],
    });

    // 2. Exchange the code for an access token via your backend
    // Since this is a core infrastructure setup, we might need a backend endpoint later.
    // For now, we follow the standard SDK flow.
    // In many simple activities, the SDK handles token exchange if configured or via local development.
    // But typically we'd fetch from our own /api/token.
    // Let's assume we just want to show user info which we might get from authenticate() command
    
    const auth = await discordSdk.commands.authenticate({
        code,
    });

    return auth;
}

// Start the setup process
window.addEventListener('DOMContentLoaded', setup);
