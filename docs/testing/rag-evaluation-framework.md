## RAG Evaluation Framework

A dedicated framework to measure and improve the quality of the Retrieval-Augmented Generation pipeline.

**Retrieval Quality Metrics:**
-   **Hit Rate**: Percentage of queries for which the correct document is in the top-k results.
-   **MRR (Mean Reciprocal Rank)**: The average of the reciprocal ranks of the correct answer. Punishes systems that return the correct answer at a lower rank.
-   **Precision@k**: The proportion of retrieved documents in the top-k that are relevant.

**Generation Quality Metrics:**
-   **Citation Precision & Recall**:
    -   *Precision*: Of the citations made, what proportion are correct?
    -   *Recall*: Of the citations that *should* have been made, what proportion were?
-   **Factual Consistency Score**: Using an NLI (Natural Language Inference) model to check if the generated answer `entails` or `contradicts` the source text.
-   **Answer Relevance**: How well the generated answer addresses the user's query.

**Human Evaluation Rubric:**
A 1-5 scale for human reviewers to rate responses on:
1.  **Relevance**: Is the answer relevant to the query?
2.  **Accuracy**: Is the information factually correct according to the source?
3.  **Completeness**: Does the answer address all parts of the query?
4.  **Clarity**: Is the answer easy to understand?
5.  **Citation Quality**: Are the citations accurate and helpful?
