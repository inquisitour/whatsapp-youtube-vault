const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// Target WhatsApp groups and their exact names
const TARGET_GROUPS = new Set(["Elephanta", "XEconomics", "G-Lab"]);

// Output file path
const DATA_DIR = path.resolve(__dirname, "../../data");
const LINKS_FILE = path.join(DATA_DIR, "links.jsonl");

// YouTube URL regex — catches all common variants
const YOUTUBE_REGEX =
  /https?:\/\/(?:www\.)?(?:youtube\.com\/(?:watch\?[^\s]*v=|shorts\/|embed\/|v\/)|youtu\.be\/|music\.youtube\.com\/watch\?[^\s]*v=)[a-zA-Z0-9_-]{11}[^\s]*/gi;

/**
 * Ensure the data directory exists.
 */
function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

/**
 * Extract all YouTube URLs from a message text.
 * @param {string} text - The message body.
 * @returns {string[]} Array of YouTube URLs found.
 */
function extractYouTubeUrls(text) {
  if (!text) return [];
  const matches = text.match(YOUTUBE_REGEX);
  return matches ? [...new Set(matches)] : [];
}

/**
 * Append a link entry as a JSON line to the JSONL file.
 * @param {object} entry - The link entry to write.
 */
function appendToJsonl(entry) {
  const line = JSON.stringify(entry) + "\n";
  fs.appendFileSync(LINKS_FILE, line, "utf8");
}

/**
 * Main function — initializes the WhatsApp Web client and starts listening.
 */
async function main() {
  ensureDataDir();

  const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
  });

  client.on("qr", (qr) => {
    console.log("[Monitor] Scan this QR code with WhatsApp:");
    qrcode.generate(qr, { small: true });
  });

  client.on("ready", () => {
    console.log("[Monitor] WhatsApp Web client is ready!");
    console.log(
      `[Monitor] Watching groups: ${[...TARGET_GROUPS].join(", ")}`
    );
  });

  client.on("authenticated", () => {
    console.log("[Monitor] Authenticated successfully.");
  });

  client.on("auth_failure", (msg) => {
    console.error("[Monitor] Authentication failed:", msg);
    process.exit(1);
  });

  client.on("message_create", async (message) => {
    try {
      const chat = await message.getChat();

      // Only process group messages from target groups
      if (!chat.isGroup || !TARGET_GROUPS.has(chat.name)) {
        return;
      }

      const urls = extractYouTubeUrls(message.body);
      if (urls.length === 0) {
        return;
      }

      const contact = await message.getContact();
      const sender = contact.pushname || contact.number || "Unknown";

      const entry = {
        timestamp: new Date().toISOString(),
        group_name: chat.name,
        sender: sender,
        youtube_urls: urls,
        message_text: message.body,
        message_id: message.id._serialized,
      };

      appendToJsonl(entry);
      console.log(
        `[Monitor] [${chat.name}] ${urls.length} YouTube link(s) from ${sender}`
      );
    } catch (err) {
      console.error("[Monitor] Error processing message:", err.message);
    }
  });

  // Graceful shutdown
  const shutdown = async () => {
    console.log("\n[Monitor] Shutting down gracefully...");
    try {
      await client.destroy();
    } catch (err) {
      // Ignore errors during shutdown
    }
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  console.log("[Monitor] Initializing WhatsApp Web client...");
  await client.initialize();
}

main().catch((err) => {
  console.error("[Monitor] Fatal error:", err);
  process.exit(1);
});
