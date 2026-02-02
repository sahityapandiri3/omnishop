'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { projectsAPI, ProjectListItem } from '@/utils/api';
import { PlusIcon, TrashIcon, FolderIcon } from '@heroicons/react/24/outline';
import { ProtectedRoute } from '@/components/ProtectedRoute';

function ProjectsPageContent() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Fetch projects
  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects();
    }
  }, [isAuthenticated]);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await projectsAPI.list();
      setProjects(response.projects);
    } catch (err: any) {
      console.error('Failed to fetch projects:', err);
      setError('Failed to load projects. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = () => {
    // Clear sessionStorage to start fresh - don't carry over images from previous projects
    sessionStorage.removeItem('roomImage');
    sessionStorage.removeItem('cleanRoomImage');
    sessionStorage.removeItem('curatedRoomImage');
    sessionStorage.removeItem('curatedVisualizationImage');
    sessionStorage.removeItem('preselectedProducts');
    sessionStorage.removeItem('persistedCanvasProducts');
    sessionStorage.removeItem('design_session_id');
    sessionStorage.removeItem('onboardingPreferences');
    console.log('[ProjectsPage] Cleared sessionStorage for new project');

    // Navigate to onboarding flow - project will be created at the end
    router.push('/onboarding');
  };

  const handleDeleteProject = async (projectId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!confirm('Are you sure you want to delete this project? This cannot be undone.')) {
      return;
    }

    try {
      setDeleting(projectId);
      await projectsAPI.delete(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } catch (err: any) {
      console.error('Failed to delete project:', err);
      setError('Failed to delete project. Please try again.');
    } finally {
      setDeleting(null);
    }
  };

  const formatDate = (dateString: string) => {
    // Parse the date - backend returns UTC timestamps
    // Append 'Z' if not present to ensure it's treated as UTC
    const normalizedDateString = dateString.endsWith('Z') ? dateString : dateString + 'Z';
    const date = new Date(normalizedDateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">My Projects</h1>
            <p className="mt-1 text-gray-600">
              {projects.length === 0
                ? 'Start your first design project'
                : `${projects.length} project${projects.length === 1 ? '' : 's'}`}
            </p>
          </div>
          <button
            onClick={handleCreateProject}
            className="inline-flex items-center gap-2 px-4 py-2 bg-neutral-800 text-white font-medium rounded-lg hover:bg-neutral-900 transition-colors shadow-sm"
          >
            <PlusIcon className="w-5 h-5" />
            New Project
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 text-red-500 hover:text-red-700"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-xl border border-gray-200 overflow-hidden animate-pulse"
              >
                <div className="aspect-video bg-gray-200" />
                <div className="p-4">
                  <div className="h-5 bg-gray-200 rounded w-3/4 mb-2" />
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          /* Empty State */
          <div className="text-center py-16">
            <div className="mx-auto w-24 h-24 bg-neutral-100 rounded-full flex items-center justify-center mb-6">
              <FolderIcon className="w-12 h-12 text-neutral-600" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              No projects yet
            </h2>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Create your first project to start designing your dream space with AI-powered visualization.
            </p>
            <button
              onClick={handleCreateProject}
              className="inline-flex items-center gap-2 px-6 py-3 bg-neutral-800 text-white font-medium rounded-lg hover:bg-neutral-900 transition-colors shadow-lg shadow-neutral-500/25"
            >
              <PlusIcon className="w-5 h-5" />
              Create Your First Project
            </button>
          </div>
        ) : (
          /* Projects Grid */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* New Project Card */}
            <button
              onClick={handleCreateProject}
              className="group bg-white rounded-xl border-2 border-dashed border-gray-300 hover:border-neutral-500 overflow-hidden transition-all"
            >
              <div className="aspect-video flex items-center justify-center bg-gray-50 group-hover:bg-neutral-100 transition-colors">
                <PlusIcon className="w-12 h-12 text-gray-400 group-hover:text-neutral-700 transition-colors" />
              </div>
              <div className="p-4 text-center">
                <h3 className="font-medium text-gray-900 group-hover:text-neutral-700 transition-colors">
                  New Project
                </h3>
                <p className="text-sm text-gray-500">Start a new design</p>
              </div>
            </button>

            {/* Project Cards */}
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/design?projectId=${project.id}`}
                className="group bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-lg hover:border-neutral-400 transition-all"
              >
                {/* Thumbnail */}
                <div className="aspect-video relative bg-gray-100">
                  {project.has_visualization && (
                    <ProjectThumbnail projectId={project.id} />
                  )}

                  {/* Delete Button */}
                  <button
                    onClick={(e) => handleDeleteProject(project.id, e)}
                    disabled={deleting === project.id}
                    className="absolute top-2 right-2 p-2 bg-white/90 backdrop-blur rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 transition-all disabled:opacity-50"
                    title="Delete project"
                  >
                    {deleting === project.id ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600" />
                    ) : (
                      <TrashIcon className="w-4 h-4 text-red-600" />
                    )}
                  </button>

                  {/* Status Badges */}
                  <div className="absolute bottom-2 left-2 flex gap-1">
                    {/* Draft/Published Badge */}
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                      project.status === 'published'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-amber-100 text-amber-700'
                    }`}>
                      {project.status === 'published' ? 'Published' : 'Draft'}
                    </span>
                    {project.has_room_image && (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                        Room
                      </span>
                    )}
                    {project.has_visualization && (
                      <span className="px-2 py-0.5 bg-neutral-200 text-neutral-700 text-xs font-medium rounded-full">
                        Designed
                      </span>
                    )}
                  </div>
                </div>

                {/* Project Info */}
                <div className="p-4">
                  <h3 className="font-medium text-gray-900 truncate group-hover:text-neutral-700 transition-colors">
                    {project.name}
                  </h3>
                  <p className="text-sm text-gray-500">
                    Updated {formatDate(project.updated_at)}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Separate component for lazy loading thumbnails
function ProjectThumbnail({ projectId }: { projectId: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const fetchThumbnail = async () => {
      try {
        const response = await projectsAPI.getThumbnail(projectId);
        if (mounted && response.visualization_image) {
          setImageUrl(response.visualization_image);
        }
      } catch (err) {
        console.error('Failed to load thumbnail:', err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchThumbnail();

    return () => {
      mounted = false;
    };
  }, [projectId]);

  if (loading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="animate-pulse bg-gray-200 w-full h-full" />
      </div>
    );
  }

  if (!imageUrl) {
    return null;
  }

  return (
    <img
      src={imageUrl}
      alt="Project visualization"
      className="absolute inset-0 w-full h-full object-cover"
    />
  );
}

export default function ProjectsPage() {
  return (
    <ProtectedRoute
      requiredRole="user"
      requiredTiers={['advanced', 'curator']}
      allowAdmin={true}
    >
      <ProjectsPageContent />
    </ProtectedRoute>
  );
}
