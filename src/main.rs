use std::{collections::HashMap, env, fs, path::Path, sync::Arc};

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use teloxide::{prelude::*, utils::command::BotCommands};
use tokio::sync::Mutex;

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct User {
    id: i64,
    username: String,
    first_name: String,
    registered: bool,
    joined: Option<DateTime<Utc>>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct Database {
    users: HashMap<i64, User>,
    waiting: Vec<i64>,
    pairs: HashMap<i64, i64>,
}

struct AppState {
    db: Mutex<Database>,
    db_path: String,
}

type SharedState = Arc<AppState>;

impl AppState {
    fn load(db_path: &str) -> Result<Self> {
        let db = match fs::read(db_path) {
            Ok(bytes) => serde_json::from_slice(&bytes).unwrap_or_default(),
            Err(_) => Database::default(),
        };
        Ok(Self { db: Mutex::new(db), db_path: db_path.to_string() })
    }

    async fn save(&self) -> Result<()> {
        let db = self.db.lock().await;
        if let Some(parent) = Path::new(&self.db_path).parent() {
            fs::create_dir_all(parent)?;
        }
        let temp = format!("{}.tmp", self.db_path);
        fs::write(&temp, serde_json::to_vec_pretty(&*db)?)?;
        fs::rename(temp, &self.db_path)?;
        Ok(())
    }
}

#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase", description = "Stranger Chaos commands:")]
enum Command {
    #[command(description = "show available commands")]
    Help,
    #[command(description = "register and start the bot")]
    Start,
    #[command(description = "find a stranger")]
    Search,
    #[command(description = "skip to a new stranger")]
    Next,
    #[command(description = "leave the current chat")]
    Stop,
    #[command(description = "view your profile")]
    Profile,
}

async fn ensure_user(msg: &Message, state: &SharedState) {
    let mut db = state.db.lock().await;
    let id = msg.chat.id;
    let user = db.users.entry(id).or_insert_with(|| User {
        id,
        username: msg.chat.username().unwrap_or_default().to_string(),
        first_name: msg.chat.first_name().unwrap_or_default().to_string(),
        registered: true,
        joined: Some(Utc::now()),
    });
    user.registered = true;
}

async fn answer(bot: Bot, msg: Message, cmd: Command, state: SharedState) -> ResponseResult<()> {
    ensure_user(&msg, &state).await;

    match cmd {
        Command::Help => {
            bot.send_message(msg.chat.id,
                "Commands:\n/start - register\n/help - show commands\n/search - find a stranger\n/next - skip partner\n/stop - leave chat\n/profile - view profile")
                .await?;
        }
        Command::Start => {
            bot.send_message(msg.chat.id, "Welcome to Stranger Chaos! Use /search to find a stranger.").await?;
        }
        Command::Search | Command::Next => {
            if matches!(cmd, Command::Next) {
                let partner = {
                    let mut db = state.db.lock().await;
                    let partner = db.pairs.remove(&msg.chat.id);
                    if let Some(partner) = partner {
                        db.pairs.remove(&partner);
                        db.waiting.retain(|id| *id != partner);
                        Some(partner)
                    } else { None }
                };
                if let Some(partner) = partner {
                    let _ = bot.send_message(partner, "Your partner ended the chat. Use /search to find someone new.").await;
                }
            }

            let id = msg.chat.id;
            let partner = {
                let mut db = state.db.lock().await;
                db.waiting.retain(|queued| *queued != id);
                if let Some(partner) = db.waiting.iter().find(|partner| **partner != id).copied() {
                    db.waiting.retain(|queued| *queued != partner);
                    db.pairs.insert(id, partner);
                    db.pairs.insert(partner, id);
                    Some(partner)
                } else {
                    db.waiting.push(id);
                    None
                }
            };

            if let Err(error) = state.save().await { tracing::error!(%error, "could not save database"); }

            if let Some(partner) = partner {
                bot.send_message(id, "You are now connected with a stranger. Say hello!").await?;
                bot.send_message(partner, "You are now connected with a stranger. Say hello!").await?;
            } else {
                bot.send_message(id, "Searching for a stranger...").await?;
            }
        }
        Command::Stop => {
            let partner = {
                let mut db = state.db.lock().await;
                db.waiting.retain(|queued| *queued != msg.chat.id);
                let partner = db.pairs.remove(&msg.chat.id);
                if let Some(partner) = partner {
                    db.pairs.remove(&partner);
                    Some(partner)
                } else { None }
            };
            if let Err(error) = state.save().await { tracing::error!(%error, "could not save database"); }
            bot.send_message(msg.chat.id, "Chat stopped.").await?;
            if let Some(partner) = partner {
                bot.send_message(partner, "Your partner ended the chat.").await?;
            }
        }
        Command::Profile => {
            let db = state.db.lock().await;
            if let Some(user) = db.users.get(&msg.chat.id) {
                let partner = db.pairs.get(&msg.chat.id).map_or("none".to_string(), |id| id.to_string());
                bot.send_message(msg.chat.id, format!(
                    "Profile\nID: {}\nName: {}\nUsername: @{}\nCurrent partner: {}",
                    user.id, user.first_name, user.username, partner
                )).await?;
            }
        }
    }
    Ok(())
}

async fn relay(bot: Bot, msg: Message, state: SharedState) -> ResponseResult<()> {
    if let Some(text) = msg.text() {
        if text.starts_with('/') { return Ok(()); }
    }

    let partner = {
        let db = state.db.lock().await;
        db.pairs.get(&msg.chat.id).copied()
    };
    if let Some(partner) = partner {
        if let Some(text) = msg.text() {
            bot.send_message(partner, text).await?;
        } else if let Some(photo) = msg.photo() {
            if let Some(file) = photo.last() {
                bot.send_photo(partner, file.file.id.clone()).await?;
            }
        }
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let token = env::var("BOT_TOKEN").expect("BOT_TOKEN must be set");
    let db_path = env::var("DB_PATH").unwrap_or_else(|_| "data/db.json".to_string());
    let state = Arc::new(AppState::load(&db_path)?);
    let bot = Bot::new(token);

    let commands = Update::filter_message()
        .filter_command::<Command>()
        .endpoint(answer);
    let messages = Update::filter_message().endpoint(relay);
    let handler = commands.branch(messages);

    Dispatcher::builder(bot, handler)
        .dependencies(dptree::deps![state])
        .build()
        .dispatch()
        .await;

    Ok(())
}
