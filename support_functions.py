from loadnsave import load_session_data, save_session_data


async def session_success(user_id, name_of_skill):
  session_data = await load_session_data()

  if user_id in session_data:
    if name_of_skill not in session_data[user_id]:
      session_data[user_id].append(name_of_skill)
      await save_session_data(session_data)
