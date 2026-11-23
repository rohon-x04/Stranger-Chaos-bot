use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use anyhow::Result;
use teloxide::{prelude::*, utils::command::BotCommands};
use tokio::sync::Mutex;

#[derive(Clone, Default)]
struct BotState {
    users: HashMap<i64, HashSet<i64>>,
}

type SharedState = Arc<Mutex<BotState>>;

#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase", description = "Stranger Chaos commands:")]
enenum Commands {
    #[command(description = "show available commands")]
    Help,
    #[command(description = "register and start the bot")]
    Start,
    #[command(description = "find a stranger")]
    Search,
    #[command(description = "leave the current search/chat")]
    Stop,
}

async fn answer(bot: Bot, msg: Message, cmd: Commands, state: SharedState) -> ResponseResult<()> {
    match cmd {
        Commands::Help | Commands::Start => {
            bot.send_message(msg.chat.id, "Welcome to Stranger Chaos! Use /search to find a stranger.")
                .await?;
        }
        Commands::Search => {
            let mut state = state.lock().await;
            let id = msg.chat.id;
            state.users.entry(id).or_default().insert(id);
            bot.send_message(id, "🔎 Searching for a stranger...").await?;
        }
        Commands::Stop => {
            let mut state = state.lock().await;
            let id = msg.chat.id;
            state.users.remove(&id);
            bot.send_message(id, "Chat stopped.").await?;
        }
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let token = std::env::var("BOT_TOKEN")
        .expect("BOT_TOKEN must be set before starting the bot");

    let bot = Bot::new(token);
    let state = Arc::new(Mutex::new(BotState::default()));

    let handler = Update::filter_message()
        .filter_command::<Commands>()
        .endpoint(answer);

    Dispatcher::builder(bot, handler)
        .dependencies(dptree::deps![state])
        .build()
        .dispatch()
        .await;

    Ok(())
}
