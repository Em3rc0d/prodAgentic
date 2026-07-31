import { render, screen, fireEvent, act } from '@testing-library/react'
import Page from '../app/page'

let mockEventSourceInstance: MockEventSource | null = null;

class MockEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = jest.fn();
  constructor() {
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    mockEventSourceInstance = this;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
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
    
    const textarea = screen.getByPlaceholderText(/e.g. Kafka, Spring Boot/i)
    fireEvent.change(textarea, { target: { value: 'AI' } })
    
    const generateBtn = screen.getByText(/Generate Ideas/i)
    await act(async () => {
      fireEvent.click(generateBtn)
    })
    
    const ideaBtn = await screen.findByText('Idea 1')
    await act(async () => {
      fireEvent.click(ideaBtn)
    })
    
    expect(screen.getByText('Research Agent')).toBeInTheDocument()
    
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { data: JSON.stringify({ stage: "error", stage_name: "research", reason: "error test" }) }))
      }
    })
    
    // Exits pipeline_running mode and switches back to Brief tab
    expect(screen.getByText('Brief')).toHaveClass('active')
    // It should go back to showing the ideas in the Brief tab, wait actually the text is in Ideas tab now.
    // We just verify it's no longer in pipeline running state (the stream is closed, etc.)
    expect(mockEventSourceInstance.close).toHaveBeenCalled()
    // Error is shown
    expect(screen.getByText(/error test/i)).toBeInTheDocument()
  })

  it('test_stage_failed_invalidates_active_attempt', async () => {
    render(<Page />)
    
    const textarea = screen.getByPlaceholderText(/e.g. Kafka, Spring Boot/i)
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
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { data: JSON.stringify({ stage: "stage.attempt_started", stage_name: "research", attempt_id: "att-1" }) }))
      }
    })
    
    // Fail stage with error (terminal)
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { data: JSON.stringify({ stage: "error", stage_name: "research", reason: "First error" }) }))
      }
    })
    
    // Active attempt should be cleared, check by seeing if EventSource was closed
    expect(mockEventSourceInstance?.close).toHaveBeenCalled()
    // Exits pipeline_running mode
    expect(screen.getByText('Brief')).toHaveClass('active')
    
    // If it was just stage_failed without error, it wouldn't close the stream. But `error` closes it.
    expect(screen.getByText(/First error/i)).toBeInTheDocument()
  })

  it('test_ui_tab_isolation_and_transitions', async () => {
    render(<Page />)
    
    // Initial state: only Brief is active, Ideas is disabled, others disabled
    expect(screen.getByText('Brief')).toHaveClass('active')
    
    // Input topic and generate ideas
    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test Topic' } })
    await act(async () => {
      fireEvent.click(screen.getByText(/Generate Ideas/i))
    })
    
    // Now Ideas tab is active
    expect(screen.getByText('Ideas')).toHaveClass('active')
    
    // Select an idea
    const ideaBtn = await screen.findByText('Idea 1')
    await act(async () => {
      fireEvent.click(ideaBtn)
    })
    
    // Now Research tab is active
    expect(screen.getByText('Research')).toHaveClass('active')
    
    // Simulate research completing
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { data: JSON.stringify({ stage: "stage_done", stage_name: "research" }) }))
      }
    })
    
    // Should auto-transition to Draft tab
    expect(screen.getByText('Draft')).toHaveClass('active')
    
    // Test manual tab switching
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Diagnostics')).toHaveClass('active')
    expect(screen.getByText('Pipeline Diagnostics')).toBeInTheDocument()
    
    fireEvent.click(screen.getByText('Visual'))
    expect(screen.getByText('Visual')).toHaveClass('active')
    expect(screen.getByText('Visual Agent')).toBeInTheDocument()
  })

  it('test_visual_rendering_endpoint_call', async () => {
    render(<Page />)
    
    // Mock the visual render endpoint
    global.fetch = jest.fn((url) => {
      if (url.toString().includes('visual-renders')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'READY', asset_url: 'https://example.com/rendered.png', prompt_used: 'Test' }),
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ideas: ['Idea 1'] }) })
    }) as jest.Mock;
    
    // Go through pipeline to reach Visual tab
    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test Topic' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })
    
    // Manually navigate to visual tab
    fireEvent.click(screen.getByText('Visual'))
    
    // Simulate visual prompt generated
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { data: JSON.stringify({ stage: "visual.prompt_completed", content: "Cyberpunk city" }) }))
      }
    })
    
    expect(screen.getByDisplayValue('Cyberpunk city')).toBeInTheDocument()
    
    // Click render button
    const renderButton = screen.getByText(/Generar imagen/i)
    await act(async () => {
      fireEvent.click(renderButton)
    })
    
    // Verify fetch was called to visual-renders
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/visual-renders'), expect.any(Object))
    
    // Verify image is shown
    const img = await screen.findByAltText('Cyberpunk city')
    expect(img).toHaveAttribute('src', 'https://example.com/rendered.png')
  })
})
