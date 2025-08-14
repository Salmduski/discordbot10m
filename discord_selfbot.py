require('dotenv').config();
const { Client, Events, GatewayIntentBits, REST, Routes, SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const translate = require('translate');

// Configuration
const MOD_ROLE_ID = '1398413061169352949';
const OWNER_IDS = ['YOUR_DISCORD_USER_ID']; // Add your Discord user ID here
const LOG_CHANNEL_ID = '1404675690007105596'; // Anti-bypass logging channel
const MAX_STRIKES = 3; // Number of strikes before mute

// Create a new client instance
const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildModeration,
        GatewayIntentBits.GuildPresences
    ] 
});

// Check if user has permission to use commands
function hasPermission(member) {
    // Check if user is owner
    if (OWNER_IDS.includes(member.id)) return true;
    
    // Check if user has the specific mod role
    if (member.roles.cache.has(MOD_ROLE_ID)) return true;
    
    return false;
}

// Anti-bypass detection patterns (FIXED REGEX)
const bypassPatterns = [
    /[\u200B-\u200D\uFEFF\u00AD]/g, // Zero-width characters
    /[\u180E\u2060\u2061\u2062\u2063\u2064\u206A-\u206F]/g, // Invisible characters
    /[\uDB40\uDC00-\uDB7F\uDFF0-\uDFFF]/g, // Unicode surrogates (FIXED)
    /[\uE000-\uF8FF]/g, // Private use area
    /[\uFFF0-\uFFFF]/g, // Specials block
    /[\uD83D\uDC70-\uD83D\uDC78]/g, // Zalgo-style emojis
    /[\u2600-\u26FF]/g, // Miscellaneous symbols
    /[\u2700-\u27BF]/g, // Dingbats
    /[\u1F600-\u1F64F]/g, // Emoticons
    /[\u1F300-\u1F5FF]/g, // Miscellaneous Symbols and Pictographs
    /[\u1F680-\u1F6FF]/g, // Transport and Map Symbols
    /[\u1F1E6-\u1F1FF]{2,}/g, // Regional indicator symbols (flags)
    /[\u23F0-\u23FA]/g, // Miscellaneous Technical
    /[\u25A0-\u25FF]/g, // Geometric Shapes
    /[\u2B50]/g, // Star emoji
    /[\u2764]/g, // Heart emoji
    /[\u20E3]/g, // Combining enclosing keycap
    /[\u20DD-\u20E0]/g, // Enclosing marks
    /[\u0300-\u036F]/g, // Combining diacritical marks
    /[\u20D0-\u20FF]/g, // Combining diacritical marks for symbols
    /[\u1AB0-\u1AFF]/g, // Combining diacritical marks extended
    /[\u1DC0-\u1DFF]/g, // Combining diacritical marks supplement
    /[\uFE20-\uFE2F]/g, // Combining half marks
    /[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]/g, // Directional formatting
    /[\u0000-\u001F\u007F-\u009F]/g, // Control characters
    /[\u2028-\u2029]/g, // Line/paragraph separators
    /[\u2000-\u200F]/g, // General punctuation spaces
    /[\u205F-\u206F]/g, // Medium mathematical space
    /[\u3000]/g, // Ideographic space
    /[\u17B4-\u17B5]/g, // Khmer vowels
    /[\u2060]/g, // Word joiner
    /[\u00A0]/g, // Non-breaking space
];

// Check for bypass attempts
function detectBypass(content) {
    for (const pattern of bypassPatterns) {
        if (pattern.test(content)) {
            return true;
        }
    }
    return false;
}

// Log bypass attempts
async function logBypassAttempt(message, type) {
    try {
        const logChannel = await client.channels.fetch(LOG_CHANNEL_ID);
        if (!logChannel) return;

        const embed = new EmbedBuilder()
            .setTitle('🚨 Bypass Attempt Detected')
            .setColor(0xFF0000)
            .addFields(
                { name: 'User', value: `<@${message.author.id}> (${message.author.tag})`, inline: true },
                { name: 'Channel', value: `<#${message.channel.id}>`, inline: true },
                { name: 'Type', value: type, inline: true },
                { name: 'Content', value: `\`\`\`${message.content.slice(0, 1000)}\`\`\``, inline: false },
                { name: 'Message ID', value: message.id, inline: true },
                { name: 'Timestamp', value: `<t:${Math.floor(message.createdTimestamp / 1000)}:F>`, inline: true }
            )
            .setFooter({ text: 'Anti-Bypass System' })
            .setTimestamp();

        await logChannel.send({ embeds: [embed] });
    } catch (error) {
        console.error('Failed to log bypass attempt:', error);
    }
}

// Strike system
const strikes = new Map(); // userId -> strike count

function addStrike(userId, reason, moderatorId) {
    if (!strikes.has(userId)) {
        strikes.set(userId, 0);
    }
    
    const currentStrikes = strikes.get(userId) + 1;
    strikes.set(userId, currentStrikes);
    
    return currentStrikes;
}

function getStrikes(userId) {
    return strikes.get(userId) || 0;
}

function resetStrikes(userId) {
    strikes.delete(userId);
}

// Command definitions
const commands = [
    // Mute command
    new SlashCommandBuilder()
        .setName('mute')
        .setDescription('Mute a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to mute')
                .setRequired(true))
        .addIntegerOption(option =>
            option.setName('duration')
                .setDescription('Duration in minutes (default: 10)')
                .setRequired(false))
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for mute')
                .setRequired(false)),

    // Unmute command
    new SlashCommandBuilder()
        .setName('unmute')
        .setDescription('Unmute a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to unmute')
                .setRequired(true))
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for unmute')
                .setRequired(false)),

    // Purge all messages (up to 250)
    new SlashCommandBuilder()
        .setName('purge')
        .setDescription('Delete messages from channel (up to 250)')
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('Number of messages to delete (1-250)')
                .setRequired(true)),

    // Purge human messages only
    new SlashCommandBuilder()
        .setName('purgehumans')
        .setDescription('Delete messages from humans only (up to 250)')
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('Number of messages to check (1-250)')
                .setRequired(true)),

    // Purge bot messages only
    new SlashCommandBuilder()
        .setName('purgebots')
        .setDescription('Delete messages from bots only (up to 250)')
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('Number of messages to check (1-250)')
                .setRequired(true)),

    // Lock channel command with duration and reason
    new SlashCommandBuilder()
        .setName('lock')
        .setDescription('Lock the current channel temporarily')
        .addIntegerOption(option =>
            option.setName('duration')
                .setDescription('Duration in minutes (0 = permanent)')
                .setRequired(false)
                .setMinValue(0))
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for locking the channel')
                .setRequired(false)),

    // Unlock channel command
    new SlashCommandBuilder()
        .setName('unlock')
        .setDescription('Unlock the current channel'),

    // Slowmode command
    new SlashCommandBuilder()
        .setName('slowmode')
        .setDescription('Set slowmode for the current channel')
        .addIntegerOption(option =>
            option.setName('seconds')
                .setDescription('Seconds between messages (0 to disable)')
                .setRequired(true)
                .setMinValue(0)
                .setMaxValue(21600)),

    // Warn command
    new SlashCommandBuilder()
        .setName('warn')
        .setDescription('Warn a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to warn')
                .setRequired(true))
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for warning')
                .setRequired(true)),

    // Clear user messages command
    new SlashCommandBuilder()
        .setName('clearuser')
        .setDescription('Delete messages from a specific user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user whose messages to delete')
                .setRequired(true))
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('Number of messages to check (1-100)')
                .setRequired(true)
                .setMinValue(1)
                .setMaxValue(100)),

    // Role management commands
    new SlashCommandBuilder()
        .setName('addrole')
        .setDescription('Add a role to a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to add role to')
                .setRequired(true))
        .addRoleOption(option =>
            option.setName('role')
                .setDescription('The role to add')
                .setRequired(true)),

    new SlashCommandBuilder()
        .setName('removerole')
        .setDescription('Remove a role from a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to remove role from')
                .setRequired(true))
        .addRoleOption(option =>
            option.setName('role')
                .setDescription('The role to remove')
                .setRequired(true)),

    // Nickname command
    new SlashCommandBuilder()
        .setName('nick')
        .setDescription('Change a user\'s nickname')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to change nickname for')
                .setRequired(true))
        .addStringOption(option =>
            option.setName('nickname')
                .setDescription('New nickname (leave empty to reset)')
                .setRequired(false)),

    // Announce command
    new SlashCommandBuilder()
        .setName('announce')
        .setDescription('Make an announcement')
        .addStringOption(option =>
            option.setName('message')
                .setDescription('Announcement message')
                .setRequired(true))
        .addChannelOption(option =>
            option.setName('channel')
                .setDescription('Channel to send announcement to')
                .setRequired(false)),

    // Giveaway command
    new SlashCommandBuilder()
        .setName('giveaway')
        .setDescription('Start a giveaway')
        .addStringOption(option =>
            option.setName('prize')
                .setDescription('Prize for the giveaway')
                .setRequired(true))
        .addIntegerOption(option =>
            option.setName('winners')
                .setDescription('Number of winners (1-20)')
                .setRequired(true)
                .setMinValue(1)
                .setMaxValue(20))
        .addIntegerOption(option =>
            option.setName('duration')
                .setDescription('Duration in minutes (1-1440)')
                .setRequired(true)
                .setMinValue(1)
                .setMaxValue(1440))
        .addChannelOption(option =>
            option.setName('channel')
                .setDescription('Channel to host giveaway in')
                .setRequired(false)),

    // Strike commands
    new SlashCommandBuilder()
        .setName('strike')
        .setDescription('Add a strike to a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to strike')
                .setRequired(true))
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for strike')
                .setRequired(true)),

    new SlashCommandBuilder()
        .setName('strikes')
        .setDescription('Check strike count for a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to check strikes for')
                .setRequired(true)),

    new SlashCommandBuilder()
        .setName('resetstrikes')
        .setDescription('Reset strikes for a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to reset strikes for')
                .setRequired(true))
].map(command => command.toJSON());

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

// Store for temporary locks
const temporaryLocks = new Map();

// Store for warnings (in production, use a database)
const warnings = new Map();

// Store for active giveaways
const giveaways = new Map();

// Register commands
client.once(Events.ClientReady, async () => {
    console.log(`Ready! Logged in as ${client.user.tag}`);
    
    // Clear any existing temporary locks on startup
    temporaryLocks.clear();
    
    try {
        console.log('Started refreshing application (/) commands.');
        
        await rest.put(
            Routes.applicationCommands(client.user.id),
            { body: commands }
        );
        
        console.log('Successfully reloaded application (/) commands.');
    } catch (error) {
        console.error(error);
    }
});

// Handle interactions
client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isChatInputCommand()) return;

    const { commandName, options, member, channel } = interaction;

    // Check permissions
    if (!hasPermission(member)) {
        return await interaction.reply({
            content: '❌ You don\'t have permission to use this command! You need the Moderator role or be the bot owner.',
            ephemeral: true
        });
    }

    try {
        // Mute command
        if (commandName === 'mute') {
            const user = options.getUser('user');
            const duration = options.getInteger('duration') || 10;
            const reason = options.getString('reason') || 'No reason provided';
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            // Check if user can be muted
            if (!targetMember.moderatable) {
                return await interaction.reply({
                    content: '❌ I cannot mute this user! Make sure my role is higher than theirs.',
                    ephemeral: true
                });
            }

            // Check if trying to mute owner or user with higher role
            if (OWNER_IDS.includes(targetMember.id)) {
                return await interaction.reply({
                    content: '❌ You cannot mute the bot owner!',
                    ephemeral: true
                });
            }

            const muteDuration = duration * 60 * 1000; // Convert to milliseconds
            
            await targetMember.timeout(muteDuration, reason);
            
            await interaction.reply({
                content: `✅ <@${user.id}> has been muted for ${duration} minutes.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`
            });

            // Send DM to user with moderator info
            try {
                await user.send(`You have been muted in ${interaction.guild.name} for ${duration} minutes.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`);
            } catch (error) {
                console.log('Could not send DM to user');
            }
        }

        // Unmute command
        else if (commandName === 'unmute') {
            const user = options.getUser('user');
            const reason = options.getString('reason') || 'No reason provided';
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            // Check if user is currently muted
            if (!targetMember.isCommunicationDisabled()) {
                return await interaction.reply({
                    content: '❌ This user is not currently muted!',
                    ephemeral: true
                });
            }

            try {
                // Remove timeout
                await targetMember.timeout(null);
                
                await interaction.reply({
                    content: `✅ <@${user.id}> has been unmuted.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`
                });

                // Send DM to user with moderator info
                try {
                    await user.send(`You have been unmuted in ${interaction.guild.name}.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`);
                } catch (error) {
                    console.log('Could not send DM to user');
                }
            } catch (error) {
                console.error('Unmute error:', error);
                await interaction.reply({
                    content: '❌ Failed to unmute the user. They might not be muted or I don't have permission.',
                    ephemeral: true
                });
            }
        }

        // Purge all messages (up to 250)
        else if (commandName === 'purge') {
            let amount = options.getInteger('amount');

            if (amount < 1 || amount > 250) {
                return await interaction.reply({
                    content: '❌ You need to input a number between 1 and 250!',
                    ephemeral: true
                });
            }

            await interaction.deferReply({ ephemeral: true });

            try {
                let deletedCount = 0;
                let remaining = amount;

                // Discord only allows bulk delete of up to 100 messages at a time
                while (remaining > 0) {
                    const batchSize = Math.min(remaining, 100);
                    const fetched = await channel.messages.fetch({ limit: batchSize });
                    
                    if (fetched.size === 0) break; // No more messages to delete
                    
                    await channel.bulkDelete(fetched, true);
                    deletedCount += fetched.size;
                    remaining -= batchSize;

                    // Small delay to avoid rate limits
                    if (remaining > 0) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }

                const reply = await interaction.editReply({
                    content: `✅ Successfully deleted ${deletedCount} messages!`,
                    ephemeral: true
                });

                // Delete the success message after 5 seconds
                setTimeout(() => {
                    if (reply.deletable) {
                        reply.delete().catch(console.error);
                    }
                }, 5000);
            } catch (error) {
                console.error('Purge error:', error);
                await interaction.editReply({
                    content: '❌ Failed to delete messages. I might not have permission to manage messages in this channel or some messages are too old.',
                    ephemeral: true
                });
            }
        }

        // Purge human messages only
        else if (commandName === 'purgehumans') {
            let amount = options.getInteger('amount');

            if (amount < 1 || amount > 250) {
                return await interaction.reply({
                    content: '❌ You need to input a number between 1 and 250!',
                    ephemeral: true
                });
            }

            await interaction.deferReply({ ephemeral: true });

            try {
                let deletedCount = 0;
                let remaining = amount;
                let checkedCount = 0;

                // Process in batches
                while (remaining > 0 && checkedCount < 1000) { // Safety limit
                    const batchSize = Math.min(remaining, 100);
                    const fetched = await channel.messages.fetch({ limit: batchSize });
                    
                    if (fetched.size === 0) break;
                    
                    const humanMessages = fetched.filter(msg => !msg.author.bot);
                    if (humanMessages.size > 0) {
                        await channel.bulkDelete(humanMessages, true);
                        deletedCount += humanMessages.size;
                    }
                    
                    checkedCount += fetched.size;
                    remaining -= batchSize;

                    // Small delay to avoid rate limits
                    if (remaining > 0) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }

                const reply = await interaction.editReply({
                    content: `✅ Successfully deleted ${deletedCount} human messages!`,
                    ephemeral: true
                });

                // Delete the success message after 5 seconds
                setTimeout(() => {
                    if (reply.deletable) {
                        reply.delete().catch(console.error);
                    }
                }, 5000);
            } catch (error) {
                console.error('Purge humans error:', error);
                await interaction.editReply({
                    content: '❌ Failed to delete human messages. I might not have permission to manage messages in this channel or some messages are too old.',
                    ephemeral: true
                });
            }
        }

        // Purge bot messages only
        else if (commandName === 'purgebots') {
            let amount = options.getInteger('amount');

            if (amount < 1 || amount > 250) {
                return await interaction.reply({
                    content: '❌ You need to input a number between 1 and 250!',
                    ephemeral: true
                });
            }

            await interaction.deferReply({ ephemeral: true });

            try {
                let deletedCount = 0;
                let remaining = amount;
                let checkedCount = 0;

                // Process in batches
                while (remaining > 0 && checkedCount < 1000) { // Safety limit
                    const batchSize = Math.min(remaining, 100);
                    const fetched = await channel.messages.fetch({ limit: batchSize });
                    
                    if (fetched.size === 0) break;
                    
                    const botMessages = fetched.filter(msg => msg.author.bot);
                    if (botMessages.size > 0) {
                        await channel.bulkDelete(botMessages, true);
                        deletedCount += botMessages.size;
                    }
                    
                    checkedCount += fetched.size;
                    remaining -= batchSize;

                    // Small delay to avoid rate limits
                    if (remaining > 0) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }

                const reply = await interaction.editReply({
                    content: `✅ Successfully deleted ${deletedCount} bot messages!`,
                    ephemeral: true
                });

                // Delete the success message after 5 seconds
                setTimeout(() => {
                    if (reply.deletable) {
                        reply.delete().catch(console.error);
                    }
                }, 5000);
            } catch (error) {
                console.error('Purge bots error:', error);
                await interaction.editReply({
                    content: '❌ Failed to delete bot messages. I might not have permission to manage messages in this channel or some messages are too old.',
                    ephemeral: true
                });
            }
        }

        // Lock channel command with duration and reason
        else if (commandName === 'lock') {
            const duration = options.getInteger('duration') || 0; // 0 = permanent
            const reason = options.getString('reason') || 'No reason provided';

            try {
                // Update channel permissions to deny SEND_MESSAGES for @everyone
                await channel.permissionOverwrites.create(interaction.guild.roles.everyone, {
                    SendMessages: false
                });

                // Allow owners to still send messages
                for (const ownerId of OWNER_IDS) {
                    await channel.permissionOverwrites.create(ownerId, {
                        SendMessages: true
                    });
                }

                // If duration is specified, schedule unlock
                if (duration > 0) {
                    const unlockTime = Date.now() + (duration * 60 * 1000);
                    
                    await interaction.reply({
                        content: `🔒 <#${channel.id}> has been locked by <@${member.user.id}> for ${duration} minutes\n**Reason:** ${reason}`
                    });

                    // Schedule automatic unlock
                    setTimeout(async () => {
                        try {
                            // Remove the temporary lock record
                            temporaryLocks.delete(channel.id);
                            
                            // Unlock the channel
                            await channel.permissionOverwrites.create(interaction.guild.roles.everyone, {
                                SendMessages: null // Remove the overwrite
                            });
                            
                            // Remove owner-specific permissions
                            for (const ownerId of OWNER_IDS) {
                                const ownerOverwrite = channel.permissionOverwrites.cache.get(ownerId);
                                if (ownerOverwrite) {
                                    await ownerOverwrite.delete();
                                }
                            }
                            
                            // Send unlock notification
                            await channel.send({
                                content: `🔓 <#${channel.id}> has been automatically unlocked after ${duration} minutes`
                            });
                            
                            console.log(`${channel.name} automatically unlocked after ${duration} minutes`);
                        } catch (error) {
                            console.error('Auto-unlock error:', error);
                        }
                    }, duration * 60 * 1000);

                    // Store the temporary lock
                    temporaryLocks.set(channel.id, {
                        unlockTime: unlockTime,
                        moderator: member.user.tag,
                        reason: reason
                    });
                } else {
                    // Permanent lock
                    await interaction.reply({
                        content: `🔒 <#${channel.id}> has been permanently locked by <@${member.user.id}>\n**Reason:** ${reason}`
                    });
                }

                // Log to console
                console.log(`${channel.name} locked by ${member.user.tag} for ${duration} minutes - Reason: ${reason}`);
            } catch (error) {
                console.error('Lock error:', error);
                await interaction.reply({
                    content: '❌ Failed to lock the channel. I might not have permission to manage channel permissions.',
                    ephemeral: true
                });
            }
        }

        // Unlock channel command
        else if (commandName === 'unlock') {
            try {
                // Check if channel was temporarily locked
                const tempLock = temporaryLocks.get(channel.id);
                
                // Update channel permissions to allow SEND_MESSAGES for @everyone
                await channel.permissionOverwrites.create(interaction.guild.roles.everyone, {
                    SendMessages: null // Remove the overwrite
                });

                // Remove owner-specific permissions
                for (const ownerId of OWNER_IDS) {
                    const ownerOverwrite = channel.permissionOverwrites.cache.get(ownerId);
                    if (ownerOverwrite) {
                        await ownerOverwrite.delete();
                    }
                }

                // Remove from temporary locks
                temporaryLocks.delete(channel.id);

                if (tempLock) {
                    await interaction.reply({
                        content: `🔓 <#${channel.id}> has been unlocked by <@${member.user.id}>\nIt was originally locked by ${tempLock.moderator} for reason: ${tempLock.reason}`
                    });
                } else {
                    await interaction.reply({
                        content: `🔓 <#${channel.id}> has been unlocked by <@${member.user.id}>`
                    });
                }

                // Log to console
                console.log(`${channel.name} unlocked by ${member.user.tag}`);
            } catch (error) {
                console.error('Unlock error:', error);
                await interaction.reply({
                    content: '❌ Failed to unlock the channel. I might not have permission to manage channel permissions.',
                    ephemeral: true
                });
            }
        }

        // Slowmode command
        else if (commandName === 'slowmode') {
            const seconds = options.getInteger('seconds');

            try {
                await channel.setRateLimitPerUser(seconds);
                
                if (seconds === 0) {
                    await interaction.reply({
                        content: `⏱️ Slowmode has been disabled in <#${channel.id}> by <@${member.user.id}>`
                    });
                } else {
                    await interaction.reply({
                        content: `⏱️ Slowmode has been set to ${seconds} seconds in <#${channel.id}> by <@${member.user.id}>`
                    });
                }

                // Log to console
                console.log(`Slowmode set to ${seconds} seconds in ${channel.name} by ${member.user.tag}`);
            } catch (error) {
                console.error('Slowmode error:', error);
                await interaction.reply({
                    content: '❌ Failed to set slowmode. I might not have permission to manage channel settings.',
                    ephemeral: true
                });
            }
        }

        // Warn command
        else if (commandName === 'warn') {
            const user = options.getUser('user');
            const reason = options.getString('reason');
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            // Store warning (in production, use a database)
            if (!warnings.has(user.id)) {
                warnings.set(user.id, []);
            }
            const userWarnings = warnings.get(user.id);
            userWarnings.push({
                reason: reason,
                moderator: member.user.tag,
                timestamp: new Date()
            });

            await interaction.reply({
                content: `⚠️ <@${user.id}> has been warned.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`
            });

            // Send DM to user
            try {
                await user.send(`You have been warned in ${interaction.guild.name}.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`);
            } catch (error) {
                console.log('Could not send DM to user');
            }
        }

        // Clear user messages command
        else if (commandName === 'clearuser') {
            const user = options.getUser('user');
            const amount = options.getInteger('amount');

            await interaction.deferReply({ ephemeral: true });

            try {
                let deletedCount = 0;
                let remaining = amount;
                let checkedCount = 0;

                // Process in batches
                while (remaining > 0 && checkedCount < 1000) { // Safety limit
                    const batchSize = Math.min(remaining, 100);
                    const fetched = await channel.messages.fetch({ limit: batchSize });
                    
                    if (fetched.size === 0) break;
                    
                    const userMessages = fetched.filter(msg => msg.author.id === user.id);
                    if (userMessages.size > 0) {
                        await channel.bulkDelete(userMessages, true);
                        deletedCount += userMessages.size;
                    }
                    
                    checkedCount += fetched.size;
                    remaining -= batchSize;

                    // Small delay to avoid rate limits
                    if (remaining > 0) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }

                const reply = await interaction.editReply({
                    content: `✅ Successfully deleted ${deletedCount} messages from <@${user.id}>!`,
                    ephemeral: true
                });

                // Delete the success message after 5 seconds
                setTimeout(() => {
                    if (reply.deletable) {
                        reply.delete().catch(console.error);
                    }
                }, 5000);
            } catch (error) {
                console.error('Clear user error:', error);
                await interaction.editReply({
                    content: '❌ Failed to delete user messages. I might not have permission to manage messages in this channel or some messages are too old.',
                    ephemeral: true
                });
            }
        }

        // Add role command
        else if (commandName === 'addrole') {
            const user = options.getUser('user');
            const role = options.getRole('role');
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            try {
                await targetMember.roles.add(role);
                await interaction.reply({
                    content: `✅ Added role <@&${role.id}> to <@${user.id}>`
                });
            } catch (error) {
                console.error('Add role error:', error);
                await interaction.reply({
                    content: '❌ Failed to add role. I might not have permission or the role is higher than my role.',
                    ephemeral: true
                });
            }
        }

        // Remove role command
        else if (commandName === 'removerole') {
            const user = options.getUser('user');
            const role = options.getRole('role');
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            try {
                await targetMember.roles.remove(role);
                await interaction.reply({
                    content: `✅ Removed role <@&${role.id}> from <@${user.id}>`
                });
            } catch (error) {
                console.error('Remove role error:', error);
                await interaction.reply({
                    content: '❌ Failed to remove role. I might not have permission or the role is higher than my role.',
                    ephemeral: true
                });
            }
        }

        // Nickname command
        else if (commandName === 'nick') {
            const user = options.getUser('user');
            const nickname = options.getString('nickname') || '';
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            try {
                await targetMember.setNickname(nickname);
                if (nickname) {
                    await interaction.reply({
                        content: `✅ Changed nickname of <@${user.id}> to ${nickname}`
                    });
                } else {
                    await interaction.reply({
                        content: `✅ Reset nickname of <@${user.id}>`
                    });
                }
            } catch (error) {
                console.error('Nickname error:', error);
                await interaction.reply({
                    content: '❌ Failed to change nickname. I might not have permission or the user has a higher role.',
                    ephemeral: true
                });
            }
        }

        // Announce command
        else if (commandName === 'announce') {
            const message = options.getString('message');
            const targetChannel = options.getChannel('channel') || channel;

            try {
                await targetChannel.send({
                    content: `📢 **Announcement**\n\n${message}\n\n*Posted by <@${member.user.id}>*`
                });
                await interaction.reply({
                    content: `✅ Announcement posted in <#${targetChannel.id}>`,
                    ephemeral: true
                });
            } catch (error) {
                console.error('Announce error:', error);
                await interaction.reply({
                    content: '❌ Failed to post announcement. I might not have permission to send messages in that channel.',
                    ephemeral: true
                });
            }
        }

        // Giveaway command
        else if (commandName === 'giveaway') {
            const prize = options.getString('prize');
            const winnerCount = options.getInteger('winners');
            const duration = options.getInteger('duration');
            const targetChannel = options.getChannel('channel') || channel;

            try {
                const endTime = Date.now() + (duration * 60 * 1000);
                
                const row = new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId('giveaway_join')
                            .setLabel('🎉 Join Giveaway')
                            .setStyle(ButtonStyle.Primary)
                    );

                const embed = new EmbedBuilder()
                    .setTitle('🎉 GIVEAWAY 🎉')
                    .setDescription(`**Prize:** ${prize}\n**Winners:** ${winnerCount}\n**Ends:** <t:${Math.floor(endTime / 1000)}:R>`)
                    .setColor(0x0099FF)
                    .setFooter({ text: 'React with 🎉 to participate!' })
                    .setTimestamp();

                const giveawayMessage = await targetChannel.send({
                    embeds: [embed],
                    components: [row]
                });

                // Store giveaway data
                giveaways.set(giveawayMessage.id, {
                    messageId: giveawayMessage.id,
                    channelId: targetChannel.id,
                    prize: prize,
                    winnerCount: winnerCount,
                    endTime: endTime,
                    participants: new Set()
                });

                // Auto-end giveaway
                setTimeout(async () => {
                    try {
                        const giveawayData = giveaways.get(giveawayMessage.id);
                        if (!giveawayData) return;

                        const channel = await client.channels.fetch(giveawayData.channelId);
                        const message = await channel.messages.fetch(giveawayData.messageId);
                        
                        // Determine winners
                        const participants = Array.from(giveawayData.participants);
                        const winners = [];
                        
                        for (let i = 0; i < giveawayData.winnerCount && participants.length > 0; i++) {
                            const randomIndex = Math.floor(Math.random() * participants.length);
                            winners.push(participants[randomIndex]);
                            participants.splice(randomIndex, 1);
                        }

                        // Update embed
                        const endedEmbed = new EmbedBuilder()
                            .setTitle('🎉 GIVEAWAY ENDED 🎉')
                            .setDescription(`**Prize:** ${giveawayData.prize}\n**Winners:** ${winners.length > 0 ? winners.map(id => `<@${id}>`).join(', ') : 'None (No participants)'}`)
                            .setColor(0x00FF00)
                            .setFooter({ text: 'Giveaway Ended' })
                            .setTimestamp();

                        await message.edit({
                            embeds: [endedEmbed],
                            components: []
                        });

                        // Announce winners
                        if (winners.length > 0) {
                            await channel.send({
                                content: `🎉 Congratulations ${winners.map(id => `<@${id}>`).join(', ')}! You won **${giveawayData.prize}**!`
                            });
                        }

                        // Remove from active giveaways
                        giveaways.delete(giveawayMessage.id);
                    } catch (error) {
                        console.error('Giveaway end error:', error);
                    }
                }, duration * 60 * 1000);

                await interaction.reply({
                    content: `✅ Giveaway started in <#${targetChannel.id}>!`,
                    ephemeral: true
                });
            } catch (error) {
                console.error('Giveaway error:', error);
                await interaction.reply({
                    content: '❌ Failed to start giveaway. I might not have permission to send messages in that channel.',
                    ephemeral: true
                });
            }
        }

        // Strike command
        else if (commandName === 'strike') {
            const user = options.getUser('user');
            const reason = options.getString('reason');
            
            const targetMember = await interaction.guild.members.fetch(user.id);
            
            if (!targetMember) {
                return await interaction.reply({
                    content: '❌ User not found!',
                    ephemeral: true
                });
            }

            const strikeCount = addStrike(user.id, reason, member.user.id);
            
            let response = `⚠️ Strike #${strikeCount} added to <@${user.id}>.\n**Reason:** ${reason}\n**Moderator:** <@${member.user.id}>`;
            
            // Auto-mute if max strikes reached
            if (strikeCount >= MAX_STRIKES) {
                try {
                    await targetMember.timeout(60 * 60 * 1000, `Max strikes reached (${strikeCount})`);
                    response += `\n\n✅ User has been automatically muted for 1 hour due to reaching ${MAX_STRIKES} strikes.`;
                    resetStrikes(user.id);
                } catch (error) {
                    console.error('Auto-mute error:', error);
                    response += `\n\n❌ Failed to auto-mute user.`;
                }
            }

            await interaction.reply({
                content: response
            });

            // Send DM to user
            try {
                await user.send(`You have received a strike in ${interaction.guild.name}.\n**Reason:** ${reason}\n**Strike Count:** ${strikeCount}/${MAX_STRIKES}\n**Moderator:** <@${member.user.id}>`);
            } catch (error) {
                console.log('Could not send DM to user');
            }
        }

        // Check strikes command
        else if (commandName === 'strikes') {
            const user = options.getUser('user');
            const strikeCount = getStrikes(user.id);
            
            await interaction.reply({
                content: `📊 <@${user.id}> has ${strikeCount}/${MAX_STRIKES} strikes.`,
                ephemeral: true
            });
        }

        // Reset strikes command
        else if (commandName === 'resetstrikes') {
            const user = options.getUser('user');
            resetStrikes(user.id);
            
            await interaction.reply({
                content: `✅ Strikes reset for <@${user.id}>.`,
                ephemeral: true
            });
        }

    } catch (error) {
        console.error(error);
        if (!interaction.replied && !interaction.deferred) {
            await interaction.reply({
                content: '❌ There was an error while executing this command!',
                ephemeral: true
            });
        } else if (interaction.deferred) {
            await interaction.editReply({
                content: '❌ There was an error while executing this command!',
                ephemeral: true
            });
        }
    }
});

// Handle giveaway button interactions
client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'giveaway_join') return;

    const giveawayData = giveaways.get(interaction.message.id);
    if (!giveawayData) {
        return await interaction.reply({
            content: '❌ This giveaway has ended or is no longer valid!',
            ephemeral: true
        });
    }

    if (giveawayData.participants.has(interaction.user.id)) {
        return await interaction.reply({
            content: '❌ You have already joined this giveaway!',
            ephemeral: true
        });
    }

    giveawayData.participants.add(interaction.user.id);
    await interaction.reply({
        content: '✅ You have successfully joined the giveaway!',
        ephemeral: true
    });
});

// Anti-bypass message scanning
client.on(Events.MessageCreate, async message => {
    // Ignore bot messages and commands
    if (message.author.bot) return;
    if (message.content.startsWith('/')) return;

    // Check for bypass attempts
    if (detectBypass(message.content)) {
        try {
            await message.delete();
            await logBypassAttempt(message, 'Unicode Bypass');
            
            // Warn user
            await message.author.send({
                content: `⚠️ Your message in ${message.guild.name} was removed for containing bypass characters.\nPlease refrain from using such content.`
            }).catch(() => {});
        } catch (error) {
            console.error('Failed to handle bypass message:', error);
        }
    }
});

// Language translation (Free)
client.on(Events.MessageCreate, async message => {
    // Ignore bot messages and commands
    if (message.author.bot) return;
    if (message.content.startsWith('/')) return;

    try {
        // Auto-detect language and translate to English
        const translated = await translate(message.content, { to: 'en' });
        
        // If translation happened (different from original)
        if (translated && translated !== message.content) {
            // Reply with translation
            await message.reply({
                content: `🔤 **Translation:**\n${translated}`,
                allowedMentions: { repliedUser: false }
            });
        }
    } catch (error) {
        // Ignore translation errors
        console.error('Translation error:', error);
    }
});

// Login to Discord
client.login(process.env.DISCORD_TOKEN);
