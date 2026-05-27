/**
 * Task Force AI — Armory Node Catalog
 *
 * 90+ named integrations mapped to our 8 canonical executor types
 * (trigger/llm/condition/action/http_request/webhook/database/transform).
 *
 * Each catalog entry renders as a "named node" in the Add Node menu so
 * the canvas feels as rich as n8n, while the backend executor still only
 * needs to understand the canonical type. The `service` slug + `data` shape
 * lets future per-service handlers branch on it.
 */

export const CATEGORIES = [
  "Triggers",
  "Core",
  "AI / LLM",
  "Communication",
  "Productivity",
  "CRM & Sales",
  "Social",
  "E-commerce",
  "Database",
  "Cloud & DevOps",
  "Payments",
  "Files & Storage",
  "Utility",
];

// icon names refer to lucide-react icons already imported in Studio.jsx
const NODES = [
  // ── Triggers (canonical: trigger / webhook) ──────────────────────────────
  { service: "manual",      label: "Manual Trigger",   category: "Triggers",      type: "trigger",     icon: "Play",          color: "#22d3ee", desc: "Run the workflow on demand",            data: { source: "manual" } },
  { service: "schedule",    label: "Schedule",         category: "Triggers",      type: "trigger",     icon: "Calendar",      color: "#22d3ee", desc: "Cron-style recurring trigger",          data: { source: "schedule", cron: "0 9 * * *" } },
  { service: "webhook_in",  label: "Webhook Trigger",  category: "Triggers",      type: "webhook",     icon: "Zap",           color: "#22d3ee", desc: "Inbound HTTP webhook",                  data: { source: "webhook", method: "POST" } },
  { service: "email_trig",  label: "Email Trigger",    category: "Triggers",      type: "trigger",     icon: "Mail",          color: "#22d3ee", desc: "On new email received",                 data: { source: "email", filter: "" } },
  { service: "form",        label: "Form Submission",  category: "Triggers",      type: "trigger",     icon: "FileInput",     color: "#22d3ee", desc: "Submitted form payload",                data: { source: "form" } },
  { service: "chat_trig",   label: "Chat Message",     category: "Triggers",      type: "trigger",     icon: "MessageCircle", color: "#22d3ee", desc: "Incoming chat message",                 data: { source: "chat" } },
  { service: "rss",         label: "RSS Feed",         category: "Triggers",      type: "trigger",     icon: "Rss",           color: "#22d3ee", desc: "New RSS item polled",                   data: { source: "rss", url: "" } },
  { service: "file_change", label: "File Change",      category: "Triggers",      type: "trigger",     icon: "FolderOpen",    color: "#22d3ee", desc: "Watch folder for new files",            data: { source: "filewatch", path: "" } },
  { service: "github_trig", label: "GitHub Webhook",   category: "Triggers",      type: "webhook",     icon: "GitBranch",     color: "#22d3ee", desc: "GitHub push / PR / issue event",        data: { source: "github", event: "push" } },
  { service: "stripe_trig", label: "Stripe Event",     category: "Triggers",      type: "webhook",     icon: "CreditCard",    color: "#22d3ee", desc: "Stripe webhook event",                  data: { source: "stripe", event: "charge.succeeded" } },

  // ── Core (transform / condition / http) ──────────────────────────────────
  { service: "http",        label: "HTTP Request",     category: "Core",          type: "http_request",icon: "Globe",         color: "#5B21B6", desc: "Call any REST endpoint",                data: { method: "GET", url: "" } },
  { service: "code",        label: "Code",             category: "Core",          type: "transform",   icon: "Code",          color: "#9333EA", desc: "Run custom Python (RESULT = ...)",      data: { code: "RESULT = INPUT" } },
  { service: "function",    label: "Function",         category: "Core",          type: "transform",   icon: "FunctionSquare",color: "#9333EA", desc: "Map/transform JSON items",              data: { code: "RESULT = [x for x in INPUT]" } },
  { service: "set",         label: "Set Variables",    category: "Core",          type: "transform",   icon: "PencilLine",    color: "#9333EA", desc: "Set / override fields on payload",      data: { code: "RESULT = {**INPUT, 'foo':'bar'}" } },
  { service: "if",          label: "IF",               category: "Core",          type: "condition",   icon: "Split",         color: "#0891b2", desc: "Boolean branch",                        data: { condition: "INPUT > 0" } },
  { service: "switch",      label: "Switch",           category: "Core",          type: "condition",   icon: "GitBranch",     color: "#0891b2", desc: "Multi-way route by value",              data: { condition: "INPUT.kind == 'A'" } },
  { service: "merge",       label: "Merge",            category: "Core",          type: "transform",   icon: "Combine",       color: "#9333EA", desc: "Combine two branches",                  data: { strategy: "append" } },
  { service: "loop",        label: "Loop / Iterate",   category: "Core",          type: "transform",   icon: "Repeat",        color: "#9333EA", desc: "Iterate over a list",                   data: { over: "INPUT" } },
  { service: "wait",        label: "Wait",             category: "Core",          type: "transform",   icon: "Timer",         color: "#9333EA", desc: "Sleep for N seconds",                   data: { seconds: 5 } },
  { service: "filter",      label: "Filter",           category: "Core",          type: "condition",   icon: "Filter",        color: "#0891b2", desc: "Drop items that fail predicate",        data: { condition: "INPUT.amount > 0" } },
  { service: "noop",        label: "No-Op",            category: "Core",          type: "transform",   icon: "Circle",        color: "#9333EA", desc: "Pass-through (used for branching)",     data: {} },
  { service: "webhook_out", label: "Webhook Out",      category: "Core",          type: "webhook",     icon: "Send",          color: "#C084FC", desc: "Outbound webhook POST",                 data: { url: "", method: "POST" } },

  // ── AI / LLM ─────────────────────────────────────────────────────────────
  { service: "llm",         label: "LLM (Platform)",   category: "AI / LLM",      type: "llm",         icon: "Brain",         color: "#06b6d4", desc: "Gemini 2.5 Flash (platform-managed)",   data: { prompt: "", temperature: 0.5 } },
  { service: "openai",      label: "OpenAI",           category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "GPT-5.x via BYOK",                      data: { provider: "openai", model: "gpt-5.4", prompt: "" } },
  { service: "anthropic",   label: "Anthropic",        category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Claude via BYOK",                       data: { provider: "anthropic", model: "claude-sonnet-4-6", prompt: "" } },
  { service: "gemini",      label: "Google Gemini",    category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Gemini via BYOK",                       data: { provider: "gemini", model: "gemini-2.5-pro", prompt: "" } },
  { service: "ollama",      label: "Ollama (local)",   category: "AI / LLM",      type: "llm",         icon: "Server",        color: "#06b6d4", desc: "Local Ollama runtime",                  data: { provider: "ollama", model: "llama3" } },
  { service: "ai_agent",    label: "AI Agent",         category: "AI / LLM",      type: "llm",         icon: "Bot",           color: "#06b6d4", desc: "Reasoning loop with tools",             data: { tools: [], objective: "" } },
  { service: "embedding",   label: "Embeddings",       category: "AI / LLM",      type: "llm",         icon: "Atom",          color: "#06b6d4", desc: "Vector embedding generation",           data: { provider: "openai", model: "text-embedding-3-large" } },
  { service: "vector_db",   label: "Vector Store",     category: "AI / LLM",      type: "database",    icon: "Layers",        color: "#4C1D95", desc: "Pinecone / Qdrant / Weaviate",          data: { provider: "pinecone", index: "" } },
  { service: "rag_query",   label: "RAG Query",        category: "AI / LLM",      type: "llm",         icon: "BookOpen",      color: "#06b6d4", desc: "Retrieve + generate",                   data: { top_k: 5 } },
  { service: "whisper",     label: "Whisper STT",      category: "AI / LLM",      type: "llm",         icon: "Mic",           color: "#06b6d4", desc: "Audio → transcript",                    data: { provider: "openai" } },
  { service: "tts",         label: "Text-to-Speech",   category: "AI / LLM",      type: "llm",         icon: "Volume2",       color: "#06b6d4", desc: "ElevenLabs / OpenAI TTS",               data: { provider: "elevenlabs", voice: "" } },
  { service: "image_gen",   label: "Image Generation", category: "AI / LLM",      type: "llm",         icon: "Image",         color: "#06b6d4", desc: "Nano Banana / GPT-Image / DALL·E",      data: { provider: "gemini-nano-banana", prompt: "" } },
  { service: "video_gen",   label: "Video Generation", category: "AI / LLM",      type: "llm",         icon: "Film",          color: "#06b6d4", desc: "Sora / Runway / Pika",                  data: { provider: "sora", prompt: "" } },

  // ── Communication ────────────────────────────────────────────────────────
  { service: "email_send",  label: "Send Email",       category: "Communication", type: "action",      icon: "Send",          color: "#0e7490", desc: "Generic SMTP send",                     data: { to: "", subject: "", body: "" } },
  { service: "gmail",       label: "Gmail",            category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Gmail send/read (OAuth)",               data: { service: "gmail", op: "send" } },
  { service: "sendgrid",    label: "SendGrid",         category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Transactional email API",               data: { service: "sendgrid" } },
  { service: "resend",      label: "Resend",           category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Resend.com API",                        data: { service: "resend" } },
  { service: "mailgun",     label: "Mailgun",          category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Mailgun email",                         data: { service: "mailgun" } },
  { service: "slack",       label: "Slack",            category: "Communication", type: "action",      icon: "Hash",          color: "#0e7490", desc: "Post to Slack channel",                 data: { service: "slack", channel: "#general" } },
  { service: "discord",     label: "Discord",          category: "Communication", type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Post via Discord webhook",              data: { service: "discord" } },
  { service: "telegram",    label: "Telegram",         category: "Communication", type: "action",      icon: "Send",          color: "#0e7490", desc: "Send via Telegram bot",                 data: { service: "telegram", chat_id: "" } },
  { service: "whatsapp",    label: "WhatsApp",         category: "Communication", type: "action",      icon: "Phone",         color: "#0e7490", desc: "WhatsApp Business API",                 data: { service: "whatsapp" } },
  { service: "twilio_sms",  label: "Twilio SMS",       category: "Communication", type: "action",      icon: "MessageCircle", color: "#0e7490", desc: "Send SMS via Twilio",                   data: { service: "twilio_sms" } },
  { service: "twilio_voice",label: "Twilio Voice",     category: "Communication", type: "action",      icon: "Phone",         color: "#0e7490", desc: "Outbound call via Twilio",              data: { service: "twilio_voice" } },
  { service: "msteams",     label: "MS Teams",         category: "Communication", type: "action",      icon: "Users",         color: "#0e7490", desc: "Post to Teams channel",                 data: { service: "msteams" } },

  // ── Productivity ─────────────────────────────────────────────────────────
  { service: "gsheets",     label: "Google Sheets",    category: "Productivity",  type: "action",      icon: "Table",         color: "#0e7490", desc: "Read/write rows",                       data: { service: "gsheets", op: "append" } },
  { service: "gdocs",       label: "Google Docs",      category: "Productivity",  type: "action",      icon: "FileText",      color: "#0e7490", desc: "Create / edit Google Doc",              data: { service: "gdocs" } },
  { service: "gdrive",      label: "Google Drive",     category: "Productivity",  type: "action",      icon: "HardDrive",     color: "#0e7490", desc: "Upload / list Drive files",             data: { service: "gdrive" } },
  { service: "gcal",        label: "Google Calendar",  category: "Productivity",  type: "action",      icon: "Calendar",      color: "#0e7490", desc: "Create / list events",                  data: { service: "gcal" } },
  { service: "notion",      label: "Notion",           category: "Productivity",  type: "action",      icon: "FileText",      color: "#0e7490", desc: "Create / update Notion page",           data: { service: "notion" } },
  { service: "airtable",    label: "Airtable",         category: "Productivity",  type: "database",    icon: "Table",         color: "#4C1D95", desc: "Read/write Airtable base",              data: { service: "airtable" } },
  { service: "trello",      label: "Trello",           category: "Productivity",  type: "action",      icon: "Trello",        color: "#0e7490", desc: "Trello card / board ops",               data: { service: "trello" } },
  { service: "asana",       label: "Asana",            category: "Productivity",  type: "action",      icon: "CheckSquare",   color: "#0e7490", desc: "Asana task ops",                        data: { service: "asana" } },
  { service: "jira",        label: "Jira",             category: "Productivity",  type: "action",      icon: "Bug",           color: "#0e7490", desc: "Jira issue ops",                        data: { service: "jira" } },
  { service: "clickup",     label: "ClickUp",          category: "Productivity",  type: "action",      icon: "CheckSquare",   color: "#0e7490", desc: "ClickUp task ops",                      data: { service: "clickup" } },
  { service: "monday",      label: "Monday.com",       category: "Productivity",  type: "action",      icon: "CheckSquare",   color: "#0e7490", desc: "Monday board item ops",                 data: { service: "monday" } },
  { service: "linear",      label: "Linear",           category: "Productivity",  type: "action",      icon: "CheckSquare",   color: "#0e7490", desc: "Linear issue ops",                      data: { service: "linear" } },

  // ── CRM & Sales ──────────────────────────────────────────────────────────
  { service: "hubspot",     label: "HubSpot",          category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Contact / deal ops",                    data: { service: "hubspot" } },
  { service: "salesforce",  label: "Salesforce",       category: "CRM & Sales",   type: "action",      icon: "Cloud",         color: "#0e7490", desc: "SF object CRUD",                        data: { service: "salesforce" } },
  { service: "pipedrive",   label: "Pipedrive",        category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Pipedrive deal ops",                    data: { service: "pipedrive" } },
  { service: "zoho_crm",    label: "Zoho CRM",         category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Zoho CRM ops",                          data: { service: "zoho_crm" } },
  { service: "intercom",    label: "Intercom",         category: "CRM & Sales",   type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Intercom conversation ops",             data: { service: "intercom" } },
  { service: "zendesk",     label: "Zendesk",          category: "CRM & Sales",   type: "action",      icon: "Headphones",    color: "#0e7490", desc: "Zendesk ticket ops",                    data: { service: "zendesk" } },

  // ── Social ───────────────────────────────────────────────────────────────
  { service: "twitter",     label: "Twitter / X",      category: "Social",        type: "action",      icon: "Twitter",       color: "#0e7490", desc: "Post tweet / search",                   data: { service: "twitter", op: "post" } },
  { service: "linkedin",    label: "LinkedIn",         category: "Social",        type: "action",      icon: "Linkedin",      color: "#0e7490", desc: "Post or message",                       data: { service: "linkedin" } },
  { service: "facebook",    label: "Facebook",         category: "Social",        type: "action",      icon: "Facebook",      color: "#0e7490", desc: "Page post / Messenger",                 data: { service: "facebook" } },
  { service: "instagram",   label: "Instagram",        category: "Social",        type: "action",      icon: "Instagram",     color: "#0e7490", desc: "Post photo / reel / story",             data: { service: "instagram", op: "post" } },
  { service: "youtube",     label: "YouTube",          category: "Social",        type: "action",      icon: "Youtube",       color: "#0e7490", desc: "Upload / comment / search",             data: { service: "youtube" } },
  { service: "reddit",      label: "Reddit",           category: "Social",        type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Post to subreddit",                     data: { service: "reddit" } },
  { service: "tiktok",      label: "TikTok",           category: "Social",        type: "action",      icon: "Video",         color: "#0e7490", desc: "Upload short / read analytics",         data: { service: "tiktok" } },
  { service: "pinterest",   label: "Pinterest",        category: "Social",        type: "action",      icon: "Image",         color: "#0e7490", desc: "Pin / board ops",                       data: { service: "pinterest" } },
  { service: "threads",     label: "Threads",          category: "Social",        type: "action",      icon: "AtSign",        color: "#0e7490", desc: "Post to Threads",                       data: { service: "threads" } },

  // ── E-commerce ───────────────────────────────────────────────────────────
  { service: "shopify",     label: "Shopify",          category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Shopify order / product ops",           data: { service: "shopify" } },
  { service: "woocommerce", label: "WooCommerce",      category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "WooCommerce REST",                      data: { service: "woocommerce" } },
  { service: "bigcommerce", label: "BigCommerce",      category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "BigCommerce ops",                       data: { service: "bigcommerce" } },
  { service: "square",      label: "Square",           category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Square payments + inventory",           data: { service: "square" } },
  { service: "etsy",        label: "Etsy",             category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Etsy listing ops",                      data: { service: "etsy" } },

  // ── Database ─────────────────────────────────────────────────────────────
  { service: "postgres",    label: "PostgreSQL",       category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "SQL query",                             data: { service: "postgres", query: "SELECT 1" } },
  { service: "mysql",       label: "MySQL",            category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "MySQL query",                           data: { service: "mysql", query: "" } },
  { service: "mongodb",     label: "MongoDB",          category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "Find / insert / update",                data: { service: "mongodb", op: "find" } },
  { service: "redis",       label: "Redis",            category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "Key/value ops",                         data: { service: "redis", op: "get" } },
  { service: "supabase",    label: "Supabase",         category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "Supabase table ops",                    data: { service: "supabase" } },
  { service: "firebase",    label: "Firebase",         category: "Database",      type: "database",    icon: "Flame",         color: "#4C1D95", desc: "Firestore / RTDB ops",                  data: { service: "firebase" } },
  { service: "dynamodb",    label: "DynamoDB",         category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "DynamoDB ops",                          data: { service: "dynamodb" } },
  { service: "snowflake",   label: "Snowflake",        category: "Database",      type: "database",    icon: "Snowflake",     color: "#4C1D95", desc: "Snowflake SQL",                         data: { service: "snowflake" } },
  { service: "bigquery",    label: "BigQuery",         category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "BigQuery SQL",                          data: { service: "bigquery" } },

  // ── Cloud & DevOps ───────────────────────────────────────────────────────
  { service: "aws_s3",      label: "AWS S3",           category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "S3 object ops",                         data: { service: "aws_s3" } },
  { service: "aws_lambda",  label: "AWS Lambda",       category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Invoke Lambda",                         data: { service: "aws_lambda" } },
  { service: "gcs",         label: "Google Cloud Storage",category: "Cloud & DevOps",type: "action",   icon: "Cloud",         color: "#0e7490", desc: "GCS object ops",                        data: { service: "gcs" } },
  { service: "azure_blob",  label: "Azure Blob",       category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Azure Blob ops",                        data: { service: "azure_blob" } },
  { service: "github",      label: "GitHub",           category: "Cloud & DevOps",type: "action",      icon: "Github",        color: "#0e7490", desc: "GitHub API: PRs / issues / files",      data: { service: "github" } },
  { service: "gitlab",      label: "GitLab",           category: "Cloud & DevOps",type: "action",      icon: "Gitlab",        color: "#0e7490", desc: "GitLab API",                            data: { service: "gitlab" } },
  { service: "bitbucket",   label: "Bitbucket",        category: "Cloud & DevOps",type: "action",      icon: "GitBranch",     color: "#0e7490", desc: "Bitbucket API",                         data: { service: "bitbucket" } },
  { service: "jenkins",     label: "Jenkins",          category: "Cloud & DevOps",type: "action",      icon: "Cog",           color: "#0e7490", desc: "Trigger Jenkins job",                   data: { service: "jenkins" } },
  { service: "docker",      label: "Docker",           category: "Cloud & DevOps",type: "action",      icon: "Container",     color: "#0e7490", desc: "Run / inspect containers",              data: { service: "docker" } },
  { service: "kubernetes",  label: "Kubernetes",       category: "Cloud & DevOps",type: "action",      icon: "Container",     color: "#0e7490", desc: "kubectl-style ops",                     data: { service: "kubernetes" } },
  { service: "datadog",     label: "Datadog",          category: "Cloud & DevOps",type: "action",      icon: "Activity",      color: "#0e7490", desc: "Datadog metric / event",                data: { service: "datadog" } },
  { service: "pagerduty",   label: "PagerDuty",        category: "Cloud & DevOps",type: "action",      icon: "AlertTriangle", color: "#0e7490", desc: "Trigger incident",                      data: { service: "pagerduty" } },

  // ── Payments ─────────────────────────────────────────────────────────────
  { service: "stripe",      label: "Stripe",           category: "Payments",      type: "action",      icon: "CreditCard",    color: "#0e7490", desc: "Charge / customer / subscription ops",  data: { service: "stripe" } },
  { service: "paypal",      label: "PayPal",           category: "Payments",      type: "action",      icon: "CreditCard",    color: "#0e7490", desc: "PayPal payment ops",                    data: { service: "paypal" } },
  { service: "razorpay",    label: "Razorpay",         category: "Payments",      type: "action",      icon: "CreditCard",    color: "#0e7490", desc: "Razorpay order / refund",               data: { service: "razorpay" } },
  { service: "lemonsqueezy",label: "Lemon Squeezy",    category: "Payments",      type: "action",      icon: "Lemon",         color: "#0e7490", desc: "Lemon Squeezy ops",                     data: { service: "lemonsqueezy" } },
  { service: "coinbase",    label: "Coinbase",         category: "Payments",      type: "action",      icon: "Bitcoin",       color: "#0e7490", desc: "Coinbase Commerce charge",              data: { service: "coinbase" } },

  // ── Files & Storage ──────────────────────────────────────────────────────
  { service: "read_file",   label: "Read File",        category: "Files & Storage",type: "action",     icon: "FileDown",      color: "#0e7490", desc: "Read file from disk / URL",             data: { service: "read_file", path: "" } },
  { service: "write_file",  label: "Write File",       category: "Files & Storage",type: "action",     icon: "FileUp",        color: "#0e7490", desc: "Write file to disk",                    data: { service: "write_file", path: "" } },
  { service: "ftp",         label: "FTP / SFTP",       category: "Files & Storage",type: "action",     icon: "Server",        color: "#0e7490", desc: "FTP transfer",                          data: { service: "ftp" } },
  { service: "compress",    label: "Compress (ZIP)",   category: "Files & Storage",type: "transform",  icon: "Archive",       color: "#9333EA", desc: "Zip / unzip payload",                   data: { service: "compress" } },
  { service: "csv",         label: "CSV Parse",        category: "Files & Storage",type: "transform",  icon: "Table",         color: "#9333EA", desc: "Parse / write CSV",                     data: { service: "csv" } },
  { service: "pdf",         label: "PDF Extract",      category: "Files & Storage",type: "transform",  icon: "FileText",      color: "#9333EA", desc: "Extract text from PDF",                 data: { service: "pdf" } },
  { service: "ocr",         label: "OCR",              category: "Files & Storage",type: "transform",  icon: "ScanText",      color: "#9333EA", desc: "Image → text",                          data: { service: "ocr" } },

  // ── Utility ──────────────────────────────────────────────────────────────
  { service: "scraper",     label: "Web Scraper",      category: "Utility",       type: "http_request",icon: "Globe",         color: "#5B21B6", desc: "Scrape HTML / extract DOM",             data: { url: "", selector: "" } },
  { service: "browser",     label: "Headless Browser", category: "Utility",       type: "http_request",icon: "Globe",         color: "#5B21B6", desc: "Playwright-style browse",               data: { url: "" } },
  { service: "translate",   label: "Translate",        category: "Utility",       type: "llm",         icon: "Languages",     color: "#06b6d4", desc: "Translate text",                        data: { to: "en" } },
  { service: "sentiment",   label: "Sentiment",        category: "Utility",       type: "llm",         icon: "Smile",         color: "#06b6d4", desc: "Classify sentiment",                    data: {} },
  { service: "summarize",   label: "Summarize",        category: "Utility",       type: "llm",         icon: "AlignLeft",     color: "#06b6d4", desc: "Summarize text",                        data: { length: "short" } },
  { service: "classify",    label: "Classify",         category: "Utility",       type: "llm",         icon: "Tags",          color: "#06b6d4", desc: "Multi-label classification",            data: { labels: [] } },
  { service: "json_parse",  label: "JSON Parse",       category: "Utility",       type: "transform",   icon: "Braces",        color: "#9333EA", desc: "Parse / stringify JSON",                data: {} },
  { service: "xml_parse",   label: "XML Parse",        category: "Utility",       type: "transform",   icon: "Braces",        color: "#9333EA", desc: "Parse XML",                             data: {} },
  { service: "regex",       label: "Regex Match",      category: "Utility",       type: "transform",   icon: "Hash",          color: "#9333EA", desc: "Extract via pattern",                   data: { pattern: "" } },
  { service: "hash",        label: "Hash / Crypto",    category: "Utility",       type: "transform",   icon: "Lock",          color: "#9333EA", desc: "sha256 / md5 / hmac",                   data: { algo: "sha256" } },
  { service: "encode",      label: "Base64",           category: "Utility",       type: "transform",   icon: "Binary",        color: "#9333EA", desc: "Base64 encode / decode",                data: { op: "encode" } },
  { service: "date",        label: "Date / Time",      category: "Utility",       type: "transform",   icon: "Clock",         color: "#9333EA", desc: "Parse / format dates",                  data: { format: "ISO" } },
  { service: "math",        label: "Math",             category: "Utility",       type: "transform",   icon: "Calculator",    color: "#9333EA", desc: "Arithmetic / stats",                    data: { op: "sum" } },
  { service: "uuid",        label: "Generate UUID",    category: "Utility",       type: "transform",   icon: "Fingerprint",   color: "#9333EA", desc: "Generate UUID v4",                      data: {} },
  { service: "qr",          label: "QR Code",          category: "Utility",       type: "transform",   icon: "QrCode",        color: "#9333EA", desc: "Generate QR PNG",                       data: {} },

  // ── AI / LLM (extended providers) ────────────────────────────────────────
  { service: "cohere",      label: "Cohere",           category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Cohere Command R / R+",                 data: { provider: "cohere", model: "command-r-plus" } },
  { service: "mistral",     label: "Mistral",          category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Mistral Large / Codestral",             data: { provider: "mistral", model: "mistral-large-latest" } },
  { service: "perplexity",  label: "Perplexity",       category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Perplexity online search",              data: { provider: "perplexity", model: "sonar-pro" } },
  { service: "groq",        label: "Groq",             category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Ultra-fast LLM inference",              data: { provider: "groq" } },
  { service: "huggingface", label: "Hugging Face",     category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "HF Inference API",                      data: { provider: "huggingface", model: "" } },
  { service: "together_ai", label: "Together AI",      category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Open-model hosting",                    data: { provider: "together" } },
  { service: "replicate",   label: "Replicate",        category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "Run any model on Replicate",            data: { provider: "replicate", model: "" } },
  { service: "fal_ai",      label: "fal.ai",           category: "AI / LLM",      type: "llm",         icon: "Sparkles",      color: "#06b6d4", desc: "fal.ai serverless inference",           data: { provider: "fal" } },
  { service: "runway",      label: "Runway",           category: "AI / LLM",      type: "llm",         icon: "Film",          color: "#06b6d4", desc: "Runway video generation",               data: { provider: "runway" } },
  { service: "pika",        label: "Pika Labs",        category: "AI / LLM",      type: "llm",         icon: "Film",          color: "#06b6d4", desc: "Pika video generation",                 data: { provider: "pika" } },
  { service: "stability",   label: "Stability AI",     category: "AI / LLM",      type: "llm",         icon: "Image",         color: "#06b6d4", desc: "Stable Diffusion XL",                   data: { provider: "stability" } },
  { service: "deepl",       label: "DeepL",            category: "AI / LLM",      type: "llm",         icon: "Languages",     color: "#06b6d4", desc: "DeepL machine translation",             data: { provider: "deepl" } },
  { service: "moderation",  label: "Moderation",       category: "AI / LLM",      type: "llm",         icon: "Shield",        color: "#06b6d4", desc: "Content safety classification",         data: { provider: "openai" } },
  { service: "ner",         label: "Named Entity",     category: "AI / LLM",      type: "llm",         icon: "Tags",          color: "#06b6d4", desc: "Extract entities from text",            data: {} },

  // ── Communication (extended) ─────────────────────────────────────────────
  { service: "mailchimp",   label: "Mailchimp",        category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Email campaigns / lists",               data: { service: "mailchimp" } },
  { service: "klaviyo",     label: "Klaviyo",          category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "E-com email + SMS",                     data: { service: "klaviyo" } },
  { service: "convertkit",  label: "ConvertKit",       category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Creator email broadcasts",              data: { service: "convertkit" } },
  { service: "activecampaign",label:"ActiveCampaign",  category: "Communication", type: "action",      icon: "Mail",          color: "#0e7490", desc: "Marketing automation",                  data: { service: "activecampaign" } },
  { service: "intercom_msg",label: "Intercom Message", category: "Communication", type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Send Intercom message",                 data: { service: "intercom" } },
  { service: "msteams_msg", label: "Teams Webhook",    category: "Communication", type: "action",      icon: "Users",         color: "#0e7490", desc: "Teams incoming webhook",                data: { service: "msteams" } },
  { service: "slack_dm",    label: "Slack DM",         category: "Communication", type: "action",      icon: "Send",          color: "#0e7490", desc: "Direct message a user",                 data: { service: "slack", op: "dm" } },
  { service: "signal",      label: "Signal",           category: "Communication", type: "action",      icon: "Send",          color: "#0e7490", desc: "Signal CLI bridge",                     data: { service: "signal" } },
  { service: "line",        label: "LINE",             category: "Communication", type: "action",      icon: "MessageCircle", color: "#0e7490", desc: "LINE messaging API",                    data: { service: "line" } },
  { service: "wechat",      label: "WeChat",           category: "Communication", type: "action",      icon: "MessageCircle", color: "#0e7490", desc: "WeChat Work API",                       data: { service: "wechat" } },
  { service: "kakaotalk",   label: "KakaoTalk",        category: "Communication", type: "action",      icon: "MessageCircle", color: "#0e7490", desc: "Kakao biz messaging",                   data: { service: "kakaotalk" } },

  // ── Productivity (extended) ──────────────────────────────────────────────
  { service: "confluence",  label: "Confluence",       category: "Productivity",  type: "action",      icon: "FileText",      color: "#0e7490", desc: "Wiki page CRUD",                        data: { service: "confluence" } },
  { service: "coda",        label: "Coda",             category: "Productivity",  type: "database",    icon: "Table",         color: "#4C1D95", desc: "Coda doc / table ops",                  data: { service: "coda" } },
  { service: "evernote",    label: "Evernote",         category: "Productivity",  type: "action",      icon: "FileText",      color: "#0e7490", desc: "Evernote note ops",                     data: { service: "evernote" } },
  { service: "onenote",     label: "OneNote",          category: "Productivity",  type: "action",      icon: "FileText",      color: "#0e7490", desc: "OneNote ops",                           data: { service: "onenote" } },
  { service: "todoist",     label: "Todoist",          category: "Productivity",  type: "action",      icon: "CheckSquare",   color: "#0e7490", desc: "Todoist task ops",                      data: { service: "todoist" } },
  { service: "calendly",    label: "Calendly",         category: "Productivity",  type: "action",      icon: "Calendar",      color: "#0e7490", desc: "Calendly meeting ops",                  data: { service: "calendly" } },
  { service: "outlook",     label: "Outlook",          category: "Productivity",  type: "action",      icon: "Mail",          color: "#0e7490", desc: "Outlook email + calendar",              data: { service: "outlook" } },
  { service: "miro",        label: "Miro",             category: "Productivity",  type: "action",      icon: "Layers",        color: "#0e7490", desc: "Miro board ops",                        data: { service: "miro" } },
  { service: "figma",       label: "Figma",            category: "Productivity",  type: "action",      icon: "Image",         color: "#0e7490", desc: "Figma file / comment ops",              data: { service: "figma" } },
  { service: "loom",        label: "Loom",             category: "Productivity",  type: "action",      icon: "Video",         color: "#0e7490", desc: "Loom video metadata",                   data: { service: "loom" } },

  // ── CRM & Sales (extended) ───────────────────────────────────────────────
  { service: "copper",      label: "Copper",           category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Copper CRM ops",                        data: { service: "copper" } },
  { service: "freshdesk",   label: "Freshdesk",        category: "CRM & Sales",   type: "action",      icon: "Headphones",    color: "#0e7490", desc: "Freshdesk ticket ops",                  data: { service: "freshdesk" } },
  { service: "helpscout",   label: "Help Scout",       category: "CRM & Sales",   type: "action",      icon: "Headphones",    color: "#0e7490", desc: "Help Scout conversation",               data: { service: "helpscout" } },
  { service: "drift",       label: "Drift",            category: "CRM & Sales",   type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Drift conversation API",                data: { service: "drift" } },
  { service: "front",       label: "Front",            category: "CRM & Sales",   type: "action",      icon: "Mail",          color: "#0e7490", desc: "Front inbox ops",                       data: { service: "front" } },
  { service: "close_crm",   label: "Close",            category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Close CRM ops",                         data: { service: "close" } },
  { service: "apollo",      label: "Apollo.io",        category: "CRM & Sales",   type: "action",      icon: "Building2",     color: "#0e7490", desc: "Apollo lead search / sequence",         data: { service: "apollo" } },

  // ── Social (extended) ────────────────────────────────────────────────────
  { service: "mastodon",    label: "Mastodon",         category: "Social",        type: "action",      icon: "AtSign",        color: "#0e7490", desc: "Toot to instance",                      data: { service: "mastodon" } },
  { service: "bluesky",     label: "Bluesky",          category: "Social",        type: "action",      icon: "AtSign",        color: "#0e7490", desc: "Post to Bluesky",                       data: { service: "bluesky" } },
  { service: "twitch",      label: "Twitch",           category: "Social",        type: "action",      icon: "Video",         color: "#0e7490", desc: "Stream / chat ops",                     data: { service: "twitch" } },
  { service: "snapchat",    label: "Snapchat",         category: "Social",        type: "action",      icon: "Image",         color: "#0e7490", desc: "Snap Ads / story",                      data: { service: "snapchat" } },
  { service: "discord_bot", label: "Discord Bot",      category: "Social",        type: "action",      icon: "MessageSquare", color: "#0e7490", desc: "Run Discord bot command",               data: { service: "discord", op: "bot" } },
  { service: "tg_channel",  label: "Telegram Channel", category: "Social",        type: "action",      icon: "Send",          color: "#0e7490", desc: "Post to channel",                       data: { service: "telegram", op: "channel" } },

  // ── E-commerce (extended) ────────────────────────────────────────────────
  { service: "magento",     label: "Magento",          category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Magento product / order",               data: { service: "magento" } },
  { service: "prestashop",  label: "PrestaShop",       category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "PrestaShop ops",                        data: { service: "prestashop" } },
  { service: "gumroad",     label: "Gumroad",          category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Gumroad sale events",                   data: { service: "gumroad" } },
  { service: "paddle",      label: "Paddle",           category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Paddle billing ops",                    data: { service: "paddle" } },
  { service: "amazon_sp",   label: "Amazon SP-API",    category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "Amazon seller central",                 data: { service: "amazon" } },
  { service: "ebay",        label: "eBay",             category: "E-commerce",    type: "action",      icon: "ShoppingBag",   color: "#0e7490", desc: "eBay listing ops",                      data: { service: "ebay" } },

  // ── Database (extended) ──────────────────────────────────────────────────
  { service: "clickhouse",  label: "ClickHouse",       category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "Columnar OLAP query",                   data: { service: "clickhouse" } },
  { service: "elasticsearch",label:"Elasticsearch",    category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "ES query / index",                      data: { service: "elasticsearch" } },
  { service: "pinecone",    label: "Pinecone",         category: "Database",      type: "database",    icon: "Layers",        color: "#4C1D95", desc: "Vector search",                         data: { service: "pinecone" } },
  { service: "qdrant",      label: "Qdrant",           category: "Database",      type: "database",    icon: "Layers",        color: "#4C1D95", desc: "Vector search",                         data: { service: "qdrant" } },
  { service: "weaviate",    label: "Weaviate",         category: "Database",      type: "database",    icon: "Layers",        color: "#4C1D95", desc: "Vector + hybrid search",                data: { service: "weaviate" } },
  { service: "chroma",      label: "Chroma",           category: "Database",      type: "database",    icon: "Layers",        color: "#4C1D95", desc: "Embedded vector DB",                    data: { service: "chroma" } },
  { service: "neo4j",       label: "Neo4j",            category: "Database",      type: "database",    icon: "GitBranch",     color: "#4C1D95", desc: "Graph DB Cypher query",                 data: { service: "neo4j" } },
  { service: "sqlite",      label: "SQLite",           category: "Database",      type: "database",    icon: "Database",      color: "#4C1D95", desc: "Local SQLite",                          data: { service: "sqlite" } },

  // ── Cloud & DevOps (extended) ────────────────────────────────────────────
  { service: "cloudflare",  label: "Cloudflare",       category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Workers / DNS / cache ops",             data: { service: "cloudflare" } },
  { service: "vercel",      label: "Vercel",           category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Vercel deploy hook",                    data: { service: "vercel" } },
  { service: "netlify",     label: "Netlify",          category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Netlify deploy / forms",                data: { service: "netlify" } },
  { service: "heroku",      label: "Heroku",           category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Heroku dyno / addon",                   data: { service: "heroku" } },
  { service: "render",      label: "Render",           category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Render service ops",                    data: { service: "render" } },
  { service: "fly_io",      label: "Fly.io",           category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "Fly machine ops",                       data: { service: "fly" } },
  { service: "sentry",      label: "Sentry",           category: "Cloud & DevOps",type: "action",      icon: "Bug",           color: "#0e7490", desc: "Sentry issue ops",                      data: { service: "sentry" } },
  { service: "betterstack", label: "Better Stack",     category: "Cloud & DevOps",type: "action",      icon: "Activity",      color: "#0e7490", desc: "Uptime + log mgmt",                     data: { service: "betterstack" } },
  { service: "statuspage",  label: "Statuspage",       category: "Cloud & DevOps",type: "action",      icon: "Activity",      color: "#0e7490", desc: "Incident updates",                      data: { service: "statuspage" } },
  { service: "opsgenie",    label: "Opsgenie",         category: "Cloud & DevOps",type: "action",      icon: "AlertTriangle", color: "#0e7490", desc: "Alert routing",                         data: { service: "opsgenie" } },
  { service: "newrelic",    label: "New Relic",        category: "Cloud & DevOps",type: "action",      icon: "Activity",      color: "#0e7490", desc: "APM event push",                        data: { service: "newrelic" } },
  { service: "circleci",    label: "CircleCI",         category: "Cloud & DevOps",type: "action",      icon: "Cog",           color: "#0e7490", desc: "Trigger CI pipeline",                   data: { service: "circleci" } },
  { service: "gh_actions",  label: "GitHub Actions",   category: "Cloud & DevOps",type: "action",      icon: "Github",        color: "#0e7490", desc: "Dispatch workflow_run",                 data: { service: "github_actions" } },
  { service: "terraform",   label: "Terraform Cloud",  category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "TF run / plan ops",                     data: { service: "terraform" } },

  // ── Payments (extended) ──────────────────────────────────────────────────
  { service: "wise",        label: "Wise",             category: "Payments",      type: "action",      icon: "CreditCard",    color: "#0e7490", desc: "Wise transfer",                         data: { service: "wise" } },
  { service: "plaid",       label: "Plaid",            category: "Payments",      type: "action",      icon: "CreditCard",    color: "#0e7490", desc: "Plaid Link / accounts",                 data: { service: "plaid" } },
  { service: "alchemy",     label: "Alchemy (Web3)",   category: "Payments",      type: "action",      icon: "Bitcoin",       color: "#0e7490", desc: "Ethereum RPC ops",                      data: { service: "alchemy" } },
  { service: "etherscan",   label: "Etherscan",        category: "Payments",      type: "http_request",icon: "Bitcoin",       color: "#5B21B6", desc: "ETH tx / address lookup",               data: { url: "https://api.etherscan.io/api" } },
  { service: "coingecko",   label: "CoinGecko",        category: "Payments",      type: "http_request",icon: "Bitcoin",       color: "#5B21B6", desc: "Crypto price feed",                     data: { url: "https://api.coingecko.com/api/v3" } },

  // ── Files & Storage (extended) ───────────────────────────────────────────
  { service: "dropbox",     label: "Dropbox",          category: "Files & Storage",type: "action",     icon: "Cloud",         color: "#0e7490", desc: "Dropbox file ops",                      data: { service: "dropbox" } },
  { service: "onedrive",    label: "OneDrive",         category: "Files & Storage",type: "action",     icon: "Cloud",         color: "#0e7490", desc: "OneDrive file ops",                     data: { service: "onedrive" } },
  { service: "box",         label: "Box",              category: "Files & Storage",type: "action",     icon: "Cloud",         color: "#0e7490", desc: "Box file ops",                          data: { service: "box" } },
  { service: "mega",        label: "MEGA",             category: "Files & Storage",type: "action",     icon: "Cloud",         color: "#0e7490", desc: "MEGA file ops",                         data: { service: "mega" } },
  { service: "imagekit",    label: "ImageKit",         category: "Files & Storage",type: "action",     icon: "Image",         color: "#0e7490", desc: "Image CDN + transforms",                data: { service: "imagekit" } },
  { service: "cloudinary",  label: "Cloudinary",       category: "Files & Storage",type: "action",     icon: "Image",         color: "#0e7490", desc: "Asset upload + transform",              data: { service: "cloudinary" } },

  // ── Analytics ────────────────────────────────────────────────────────────
  { service: "ga4",         label: "Google Analytics 4",category: "Utility",      type: "action",      icon: "Activity",      color: "#9333EA", desc: "GA4 event tracking",                    data: { service: "ga4" } },
  { service: "mixpanel",    label: "Mixpanel",         category: "Utility",       type: "action",      icon: "Activity",      color: "#9333EA", desc: "Mixpanel event ingest",                 data: { service: "mixpanel" } },
  { service: "amplitude",   label: "Amplitude",        category: "Utility",       type: "action",      icon: "Activity",      color: "#9333EA", desc: "Amplitude event ingest",                data: { service: "amplitude" } },
  { service: "segment",     label: "Segment",          category: "Utility",       type: "action",      icon: "Activity",      color: "#9333EA", desc: "Segment track / identify",              data: { service: "segment" } },
  { service: "posthog",     label: "PostHog",          category: "Utility",       type: "action",      icon: "Activity",      color: "#9333EA", desc: "PostHog event capture",                 data: { service: "posthog" } },
  { service: "hotjar",      label: "Hotjar",           category: "Utility",       type: "action",      icon: "Activity",      color: "#9333EA", desc: "Hotjar event ping",                     data: { service: "hotjar" } },

  // ── Queues / Streaming (Cloud bucket) ────────────────────────────────────
  { service: "kafka",       label: "Kafka",            category: "Cloud & DevOps",type: "action",      icon: "Combine",       color: "#0e7490", desc: "Kafka produce / consume",               data: { service: "kafka" } },
  { service: "rabbitmq",    label: "RabbitMQ",         category: "Cloud & DevOps",type: "action",      icon: "Combine",       color: "#0e7490", desc: "AMQP publish",                          data: { service: "rabbitmq" } },
  { service: "nats",        label: "NATS",             category: "Cloud & DevOps",type: "action",      icon: "Combine",       color: "#0e7490", desc: "NATS subject publish",                  data: { service: "nats" } },
  { service: "sns",         label: "AWS SNS",          category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "SNS topic publish",                     data: { service: "sns" } },
  { service: "sqs",         label: "AWS SQS",          category: "Cloud & DevOps",type: "action",      icon: "Combine",       color: "#0e7490", desc: "SQS send / receive",                    data: { service: "sqs" } },
  { service: "pubsub",      label: "Pub/Sub",          category: "Cloud & DevOps",type: "action",      icon: "Cloud",         color: "#0e7490", desc: "GCP Pub/Sub publish",                   data: { service: "pubsub" } },
  { service: "mqtt",        label: "MQTT",             category: "Cloud & DevOps",type: "action",      icon: "Send",          color: "#0e7490", desc: "MQTT broker publish",                   data: { service: "mqtt" } },

  // ── Auth / Secrets (Utility) ─────────────────────────────────────────────
  { service: "auth0",       label: "Auth0",            category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "Auth0 user mgmt",                       data: { service: "auth0" } },
  { service: "clerk",       label: "Clerk",            category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "Clerk user mgmt",                       data: { service: "clerk" } },
  { service: "supabase_auth",label:"Supabase Auth",    category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "Supabase auth ops",                     data: { service: "supabase_auth" } },
  { service: "1password",   label: "1Password",        category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "1Password CLI ops",                     data: { service: "1password" } },
  { service: "bitwarden",   label: "Bitwarden",        category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "Bitwarden vault ops",                   data: { service: "bitwarden" } },
  { service: "vault",       label: "HashiCorp Vault",  category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "Vault secret read/write",               data: { service: "vault" } },
  { service: "aws_secrets", label: "AWS Secrets Mgr",  category: "Utility",       type: "action",      icon: "Lock",          color: "#9333EA", desc: "AWS Secrets Manager",                   data: { service: "aws_secrets" } },

  // ── Core (extended logic) ────────────────────────────────────────────────
  { service: "set_multi",   label: "Set Multiple",     category: "Core",          type: "transform",   icon: "PencilLine",    color: "#9333EA", desc: "Set many fields at once",               data: { code: "RESULT = {**INPUT}" } },
  { service: "sort",        label: "Sort",             category: "Core",          type: "transform",   icon: "AlignLeft",     color: "#9333EA", desc: "Sort list by key",                      data: { key: "" } },
  { service: "dedupe",      label: "Deduplicate",      category: "Core",          type: "transform",   icon: "Filter",        color: "#9333EA", desc: "Remove duplicates",                     data: { by: "id" } },
  { service: "aggregate",   label: "Aggregate",        category: "Core",          type: "transform",   icon: "Combine",       color: "#9333EA", desc: "Reduce / sum / count",                  data: { op: "sum" } },
  { service: "split_batch", label: "Split In Batches", category: "Core",          type: "transform",   icon: "Split",         color: "#9333EA", desc: "Chunk list into batches",               data: { size: 10 } },
  { service: "jsonpath",    label: "JSONPath",         category: "Core",          type: "transform",   icon: "Braces",        color: "#9333EA", desc: "Extract via JSONPath expr",             data: { path: "$." } },
  { service: "jmespath",    label: "JMESPath",         category: "Core",          type: "transform",   icon: "Braces",        color: "#9333EA", desc: "JMESPath query",                        data: { expr: "" } },
  { service: "rename_keys", label: "Rename Keys",      category: "Core",          type: "transform",   icon: "PencilLine",    color: "#9333EA", desc: "Rename payload fields",                 data: { mapping: {} } },
  { service: "error_handler",label:"Error Handler",    category: "Core",          type: "condition",   icon: "AlertTriangle", color: "#0891b2", desc: "Catch + branch on error",               data: { catch: "exception" } },
  { service: "try_catch",   label: "Try / Catch",      category: "Core",          type: "transform",   icon: "Shield",        color: "#9333EA", desc: "Wrap step in try/catch",                data: { code: "try:\n    RESULT = INPUT\nexcept Exception as e:\n    RESULT = {'error': str(e)}" } },
  { service: "stop",        label: "Stop / Halt",      category: "Core",          type: "action",      icon: "Circle",        color: "#0e7490", desc: "Terminate workflow",                    data: { service: "stop" } },
];

export const NODE_CATALOG = NODES;

export function findCatalogEntry(service) {
  return NODES.find((n) => n.service === service);
}
