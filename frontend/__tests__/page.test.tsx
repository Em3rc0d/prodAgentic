import { render, screen, fireEvent, act } from '@testing-library/react'
import Page from '../app/page'

let mockEventSourceInstance: any;

class MockEventSource {
  onmessage: any;
  onerror: any;
  close = jest.fn();
  constructor(url: string) {
    mockEventSourceInstance = this;
  }
}

global.EventSource = MockEventSource as any;

describe('Page Component', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ideas: ['Idea 1'] }),
      })
    ) as jest.Mock;
  });

  it('test_stage_failed_exits_pipeline_running', async () => {
    render(<Page />)
    
    const textarea = screen.getByPlaceholderText(/Paste an article/i)
    fireEvent.change(textarea, { target: { value: 'AI' } })
    
    const generateBtn = screen.getByText(/Generate Ideas/i)
    await act(async () => {
      fireEvent.click(generateBtn)
    })
    
    const ideaBtn = await screen.findByText('Idea 1')
    await act(async () => {
      fireEvent.click(ideaBtn)
    })
    
    expect(screen.getByText(/Streaming the pipeline.../i)).toBeInTheDocument()
    
    act(() => {
      mockEventSourceInstance.onmessage({ data: JSON.stringify({ stage: "stage.failed", stage_name: "research", reason: "error test" }) })
    })
    
    // Exits pipeline_running mode
    expect(screen.queryByText(/Streaming the pipeline.../i)).not.toBeInTheDocument()
    // It should go back to showing the ideas
    expect(screen.getByText(/Select an idea to generate a full post/i)).toBeInTheDocument()
    // Error is shown
    expect(screen.getByText(/error test/i)).toBeInTheDocument()
  })

  it('test_stage_failed_invalidates_active_attempt', async () => {
    render(<Page />)
    
    const textarea = screen.getByPlaceholderText(/Paste an article/i)
    fireEvent.change(textarea, { target: { value: 'AI' } })
    
    const generateBtn = screen.getByText(/Generate Ideas/i)
    await act(async () => {
      fireEvent.click(generateBtn)
    })
    
    const ideaBtn = await screen.findByText('Idea 1')
    await act(async () => {
      fireEvent.click(ideaBtn)
    })
    
    // Start attempt
    act(() => {
      mockEventSourceInstance.onmessage({ data: JSON.stringify({ stage: "research", action: "attempt_started", attempt_id: "att-1" }) })
    })
    
    // Fail stage
    act(() => {
      mockEventSourceInstance.onmessage({ data: JSON.stringify({ stage: "stage.failed", stage_name: "research" }) })
    })
    
    // Active attempt should be cleared, check by seeing if EventSource was closed
    expect(mockEventSourceInstance.close).toHaveBeenCalled()
  })
})
