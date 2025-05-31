general_summary_prompt = """

I have a list of papers in the pdf formats, can you give me summary for each of the papers.  say limited to 10 sentences.

We like the summaries to focus on anything specific, such as:

    Key contributions

    Methodologies

    Results

    Limitations

    Applications

"""

detailed_summary_prompt = """

It seems okay for a simple review.  Now, I need to have more detailed summary with what they are doing, what is the novelty, impact and weakness for improvement.  Let us control the summary with the word into 2000 words. 

"""


summary_with_contribution = """


I need to improve the summary to analyze whether that weakness can be improved by our paper.  I will provide the abstract as follows.   Can you enrich the Novelities,  Imapct and weakness with five sentences for each paper, and add a new item called "Value for Our Paper"


"""
