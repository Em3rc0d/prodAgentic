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

  it('test_text_ready_and_idempotency_flow', async () => {
    render(<Page />)
    
    global.fetch = jest.fn((url, options) => {
      if (url.toString().includes('visual-renders')) {
        const body = JSON.parse((options as RequestInit).body as string)
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            render_id: 'rnd-999',
            status: 'READY',
            asset_url: 'https://example.com/output.png',
            prompt_used: body.prompt,
            provider: 'PollinationsImageAdapter'
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ideas: ['Idea 1'] }),
      })
    }) as jest.Mock

    // Topic generation and idea selection
    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })

    // Simulate pipeline.text_completed SSE event with context run_id
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "pipeline.text_completed", 
            final_status: "READY", 
            final_post: "This is the final text",
            run_id: "test-run-12345" 
          }) 
        }))
      }
    })

    // Check that we transitioned to text_ready mode and "Final" tab is active
    expect(screen.getByText('📝 Text Ready')).toBeInTheDocument()
    expect(screen.getByText('Final')).toHaveClass('active')
    expect(screen.getByText('This is the final text')).toBeInTheDocument()

    // Move to Visual tab
    fireEvent.click(screen.getByText('Visual'))
    expect(screen.getByText('Visual')).toHaveClass('active')

    // Simulate visual prompt completion
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "visual.prompt_completed", 
            content: "Scenic space view",
            run_id: "test-run-12345" 
          }) 
        }))
      }
    })

    const visualPromptTextarea = screen.getByDisplayValue('Scenic space view')
    expect(visualPromptTextarea).toBeInTheDocument()

    // Generar imagen
    const renderBtn = screen.getByText(/Generar imagen/i)
    await act(async () => {
      fireEvent.click(renderBtn)
    })

    // Verify correct run_id and idempotency_key were sent
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/visual-renders'), 
      expect.objectContaining({
        body: expect.stringContaining('"run_id":"test-run-12345"')
      })
    )
    
    const renderCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) => String(url).includes('/api/visual-renders'))
    const firstCallJson = JSON.parse(renderCalls[0][1].body)
    const firstKey = firstCallJson.idempotency_key
    expect(firstKey).toContain('test-run-12345')

    // Click render again with same parameters — should reuse idempotency key
    await act(async () => {
      fireEvent.click(renderBtn)
    })
    const secondRenderCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) => String(url).includes('/api/visual-renders'))
    const secondCallJson = JSON.parse(secondRenderCalls[1][1].body)
    expect(secondCallJson.idempotency_key).toBe(firstKey)

    // Change Aspect Ratio — should generate new idempotency key (different intent)
    const selectRatio = screen.getByLabelText(/Aspect Ratio/i)
    fireEvent.change(selectRatio, { target: { value: '1:1' } })
    await act(async () => {
      fireEvent.click(renderBtn)
    })
    const thirdRenderCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) => String(url).includes('/api/visual-renders'))
    const thirdCallJson = JSON.parse(thirdRenderCalls[2][1].body)
    expect(thirdCallJson.idempotency_key).not.toBe(firstKey)
  })

  it('test_visual_render_queued_status', async () => {
    render(<Page />)
    
    global.fetch = jest.fn((url) => {
      if (url.toString().includes('visual-renders')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            render_id: 'rnd-999',
            status: 'QUEUED',
            prompt_used: 'queued-prompt',
            provider: 'PollinationsImageAdapter'
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ideas: ['Idea 1'] }),
      })
    }) as jest.Mock

    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })

    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "visual.prompt_completed", 
            content: "queued-prompt",
            run_id: "test-run-12345" 
          }) 
        }))
      }
    })

    fireEvent.click(screen.getByText('Visual'))
    const renderBtn = screen.getByText(/Generar imagen/i)
    await act(async () => {
      fireEvent.click(renderBtn)
    })

    expect(screen.getByText(/Status: QUEUED/i)).toBeInTheDocument()
  })

  it('test_visual_render_cancelled_status', async () => {
    render(<Page />)
    
    global.fetch = jest.fn((url) => {
      if (url.toString().includes('visual-renders')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            render_id: 'rnd-999',
            status: 'CANCELLED',
            prompt_used: 'cancelled-prompt',
            provider: 'PollinationsImageAdapter'
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ideas: ['Idea 1'] }),
      })
    }) as jest.Mock

    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })

    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "visual.prompt_completed", 
            content: "cancelled-prompt",
            run_id: "test-run-12345" 
          }) 
        }))
      }
    })

    fireEvent.click(screen.getByText('Visual'))
    const renderBtn = screen.getByText(/Generar imagen/i)
    await act(async () => {
      fireEvent.click(renderBtn)
    })

    expect(screen.getByText(/Status: CANCELLED/i)).toBeInTheDocument()
  })

  it('test_visual_render_failed_status_preserves_prompt', async () => {
    render(<Page />)
    
    global.fetch = jest.fn((url) => {
      if (url.toString().includes('visual-renders')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            render_id: 'rnd-999',
            status: 'FAILED',
            prompt_used: 'failed-prompt',
            provider: 'PollinationsImageAdapter',
            error_message: 'Visual prompt rendering failed'
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ideas: ['Idea 1'] }),
      })
    }) as jest.Mock

    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })

    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "visual.prompt_completed", 
            content: "failed-prompt",
            run_id: "test-run-12345" 
          }) 
        }))
      }
    })

    fireEvent.click(screen.getByText('Visual'))
    const visualPromptTextarea = screen.getByDisplayValue('failed-prompt')
    const renderBtn = screen.getByText(/Generar imagen/i)
    await act(async () => {
      fireEvent.click(renderBtn)
    })

    expect(screen.getByText(/Status: FAILED/i)).toBeInTheDocument()
    expect(visualPromptTextarea).toBeInTheDocument()
    expect(visualPromptTextarea).toHaveValue('failed-prompt')
  })

  it('test_visual_prompt_failed_event_preserves_final_text_status', async () => {
    render(<Page />)
    
    fireEvent.change(screen.getByPlaceholderText(/e.g. Kafka/i), { target: { value: 'Test' } })
    await act(async () => { fireEvent.click(screen.getByText(/Generate Ideas/i)) })
    await act(async () => { fireEvent.click(await screen.findByText('Idea 1')) })

    // Simulate pipeline.text_completed
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "pipeline.text_completed", 
            final_status: "READY", 
            final_post: "This is the final text",
            run_id: "test-run-123" 
          }) 
        }))
      }
    })

    expect(screen.getByText('📝 Text Ready')).toBeInTheDocument()
    expect(screen.getByText('Final')).toHaveClass('active')

    // Simulate visual.prompt_failed
    act(() => {
      if (mockEventSourceInstance?.onmessage) {
        mockEventSourceInstance.onmessage(new MessageEvent('message', { 
          data: JSON.stringify({ 
            stage: "visual.prompt_failed", 
            reason: "Failure in visual model",
            run_id: "test-run-123" 
          }) 
        }))
      }
    })

    // Expect we still have final post preserved, mode is still text_ready or pipeline_done (it shouldn't break text)
    expect(screen.getByText('📝 Text Ready')).toBeInTheDocument()
    expect(screen.getByText('This is the final text')).toBeInTheDocument()
  })
})
