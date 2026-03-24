// Initialize the Discord Embedded App SDK
const discordSdk = new DiscordSDK.DiscordSDK(ACTIVITY_CLIENT_ID);

let currentUser = null;
let currentGuildId = null;
let pollInterval = null;

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

        currentUser = auth.user;
        currentGuildId = discordSdk.guildId;

        document.getElementById('status').innerText = 'Investigator Profile';
        document.getElementById('loading').style.display = 'none';
        document.getElementById('activity-content').style.display = 'block';

        // Initial fetch
        await fetchCharacterData();

        // Start polling for updates every 5 seconds
        pollInterval = setInterval(fetchCharacterData, 5000);

    } catch (error) {
        console.error('Error during Discord Activity initialization:', error);
        document.getElementById('status').innerText = 'Connection Error';
        document.getElementById('loading').innerHTML = `<p class="text-rose-400 mt-4 font-medium">Failed to awaken the Ancient Ones.</p>`;
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
    const auth = await discordSdk.commands.authenticate({
        code,
    });

    return auth;
}

/**
 * Fetch character data from the API.
 */
async function fetchCharacterData() {
    if (!currentUser) return;

    try {
        let url = `/api/activity/character?user_id=${currentUser.id}`;
        if (currentGuildId) {
            url += `&guild_id=${currentGuildId}`;
        }

        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
            updateUI(data);
            document.getElementById('character-quick-view').classList.remove('hidden');
            document.getElementById('no-character').classList.add('hidden');
        } else {
            console.warn('Character not found for user');
            document.getElementById('character-quick-view').classList.add('hidden');
            document.getElementById('no-character').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error fetching character data:', error);
    }
}

/**
 * Update the UI with fetched character data.
 */
function updateUI(char) {
    // Basic Info
    document.getElementById('char-name').innerText = char.NAME || 'Unknown';
    document.getElementById('char-occupation').innerText = char.Occupation || 'Unknown';

    // Vitals
    const hp = char.HP || 0;
    const maxHp = char['Max HP'] || hp || 1;
    const san = char.SAN || 0;
    const maxSan = char['Max SAN'] || char.POW || san || 1;
    const mp = char.MP || 0;
    const maxMp = char['Max MP'] || (char.POW ? Math.floor(char.POW / 5) : mp) || 1;

    updateProgressBar('hp', hp, maxHp);
    updateProgressBar('san', san, maxSan);
    updateProgressBar('mp', mp, maxMp);

    // Characteristics
    const stats = ['STR', 'DEX', 'POW', 'INT', 'CON', 'APP', 'SIZ', 'EDU', 'LUCK'];
    stats.forEach(stat => {
        const el = document.getElementById(`stat-${stat}`);
        if (el) {
            el.innerText = char[stat] || 0;
        }
    });
}

/**
 * Update a progress bar and its value text.
 */
function updateProgressBar(id, val, max) {
    const valEl = document.getElementById(`${id}-val`);
    const barEl = document.getElementById(`${id}-bar`);
    
    if (valEl) valEl.innerText = `${val} / ${max}`;
    if (barEl) {
        const percent = Math.min(100, Math.max(0, (val / max) * 100));
        barEl.style.width = `${percent}%`;
        
        // Dynamic colors based on percentage for SAN/HP
        if (id === 'hp' || id === 'san') {
            if (percent < 25) {
                barEl.classList.add('from-rose-700', 'to-rose-500');
            } else {
                barEl.classList.remove('from-rose-700', 'to-rose-500');
            }
        }
    }
}

/**
 * Mock roll function for characteristics.
 */
window.rollStat = function(statName) {
    console.log(`Roll requested for: ${statName}`);
    // Future expansion: Call an API to perform the roll and notify the guild.
    // For now, we provide visual feedback.
    const el = document.getElementById(`stat-${statName}`);
    if (el) {
        const originalColor = el.style.color;
        el.style.color = '#6366f1'; // indigo-500
        el.classList.add('animate-pulse');
        setTimeout(() => {
            el.style.color = originalColor;
            el.classList.remove('animate-pulse');
        }, 1000);
    }
};

// Start the setup process
window.addEventListener('DOMContentLoaded', setup);
