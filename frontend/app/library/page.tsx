'use client';

import { useEffect, useState } from 'react';
import { fetchPosts } from '@/lib/api';

export default function LibraryPage() {
  const [posts, setPosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchPosts();
        setPosts(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '8px' }}>Content Library</h1>
          <p style={{ color: 'var(--text-2)' }}>All your approved and published assets.</p>
        </div>
      </header>

      {loading ? (
        <div style={{ color: 'var(--text-3)' }}>Loading library...</div>
      ) : posts.length === 0 ? (
        <div style={{ padding: '64px', textAlign: 'center', color: 'var(--text-3)', background: 'var(--bg-1)', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '32px', marginBottom: '16px' }}>📚</div>
          <p>No content found in the library yet.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '24px' }}>
          {posts.map(post => (
            <div key={post.id} style={{ background: 'var(--bg-1)', borderRadius: '12px', border: '1px solid var(--border)', overflow: 'hidden' }}>
              {post.visual_url ? (
                <div style={{ height: '160px', backgroundImage: `url(${post.visual_url})`, backgroundSize: 'cover', backgroundPosition: 'center', borderBottom: '1px solid var(--border)' }} />
              ) : (
                <div style={{ height: '160px', background: 'var(--bg-2)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)' }}>No Visual</div>
              )}
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '10px', textTransform: 'uppercase', padding: '4px 8px', borderRadius: '4px', background: post.status === 'PUBLISHED' ? 'var(--success-dim)' : 'var(--surface)', color: post.status === 'PUBLISHED' ? 'var(--success)' : 'var(--text-2)', fontWeight: 600 }}>
                    {post.status}
                  </span>
                </div>
                <h3 style={{ fontSize: '15px', color: 'var(--text-0)', fontWeight: 600, marginBottom: '8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {post.topic || 'Untitled Post'}
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-2)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {post.final_copy}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
