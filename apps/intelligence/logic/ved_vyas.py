class VedVyas:

    def __init__(self,client,model_name,iterations=4):
        self.client = client
        self.model_name = model_name
        self.iterations = iterations

    def _build_refinement_prompt(self,original_prompt,draft,iteration_num):
        return (
            f"Original Context and User Query:\n{original_prompt}\n\n"
            f"Previous Draft (Iteration {iteration_num}):\n{draft}\n\n"
            "Instruction: Think thoroughly about this draft. Make the output better, "
            "more accurate, and more comprehensive if possible. Ensure it directly "
            "addresses the original query."
        )

    def generate_stream(self,full_prompt):
        current_prompt = full_prompt
        for i in range(1,self.iterations):
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=current_prompt
            )

            draft = response.text

            current_prompt = self._build_refinement_prompt(full_prompt, draft, i)

        return self.client.models.generate_content_stream(
            model=self.model_name,
            contents=current_prompt
        )