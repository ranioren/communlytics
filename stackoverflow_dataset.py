import pandas as pd

dfQuestions = pd.read_csv('./channel extraction/Questions.csv',
                            encoding = "ISO-8859-1",
                            usecols = ['Id','Score','Title', 'CreationDate'])
#answers table
dfAnswers = pd.read_csv('./channel extraction/Answers.csv',
                            encoding = "ISO-8859-1",
                            usecols = ['ParentId','Score','Body'],#parent id links to the questions table
                            )

dfQuestions = dfQuestions[dfQuestions['Score'] > 0]
dfAnswers = dfAnswers[dfAnswers['Score'] > 0]\
    .sort_values('Score',ascending=False)\
    .drop_duplicates(subset=['ParentId'])

qaDf = dfQuestions.merge(dfAnswers,left_on = 'Id', right_on = 'ParentId')\
    .rename(columns={'Title':'Question','Body':'Answer'})[['Question','Answer','Score_x', 'CreationDate']]

# stackQaData = []
# for index, row in qaDf.iterrows():
#     stackQaData.append(f"Question:\n{row['Question']}\n\nAnswer:\n{row['Answer']}")
    
qaDf['text'] = 'Question:\n' + qaDf['Question'] + '\n\nAnswer:\n' + qaDf['Answer']

print(qaDf.head())

# Save top 400 rows to sample.csv
sample_df = qaDf.head(400)
sample_csv_path = './channel extraction/sample.csv'
sample_df.to_csv(sample_csv_path, index=False)
print(f"Saved {len(sample_df)} rows to {sample_csv_path}")