import { useMemo } from 'react'
import type { GraphNode, NodeKind, StoryGraphResponse } from '../types/api'

interface StoryGraphViewProps {
  graph: StoryGraphResponse
  focusId: string
  affectedIds: Set<string>
}

interface Point {
  x: number
  y: number
}

const columns: { label: string; kinds: NodeKind[] }[] = [
  { label: '文化与设定', kinds: ['culture_mechanism', 'setting'] },
  { label: '人物', kinds: ['character'] },
  { label: '事件与承诺', kinds: ['event', 'commitment'] },
  { label: '场景', kinds: ['scene'] },
]

const kindLabels: Record<NodeKind, string> = {
  character: '人物',
  scene: '场景',
  event: '事件',
  setting: '设定',
  culture_mechanism: '文化机制',
  commitment: '叙事承诺',
}

function columnIndex(node: GraphNode) {
  const found = columns.findIndex((column) => column.kinds.includes(node.kind))
  return found >= 0 ? found : 2
}

function shortLabel(label: string) {
  return label.length > 15 ? `${label.slice(0, 14)}…` : label
}

export function StoryGraphView({ graph, focusId, affectedIds }: StoryGraphViewProps) {
  const layout = useMemo(() => {
    const grouped = columns.map(() => [] as GraphNode[])
    graph.nodes.forEach((node) => grouped[columnIndex(node)].push(node))
    grouped.forEach((nodes) => nodes.sort((left, right) => left.id.localeCompare(right.id)))

    const maxRows = Math.max(1, ...grouped.map((nodes) => nodes.length))
    const height = Math.max(430, maxRows * 78 + 120)
    const positions = new Map<string, Point>()

    grouped.forEach((nodes, index) => {
      const x = 105 + index * 300
      const spacing = (height - 110) / (nodes.length + 1)
      nodes.forEach((node, row) => {
        positions.set(node.id, { x, y: 70 + spacing * (row + 1) })
      })
    })

    return { height, positions }
  }, [graph.nodes])

  return (
    <div className="story-graph">
      <div className="graph-legend" aria-label="图谱图例">
        <span><i className="legend-focus" />当前机制</span>
        <span><i className="legend-affected" />传播路径 / 受影响节点</span>
        <span><i className="legend-default" />上下文节点</span>
      </div>
      <div className="story-graph__canvas">
        <svg
          aria-label="Story Graph"
          role="img"
          viewBox={`0 0 1110 ${layout.height}`}
          preserveAspectRatio="xMinYMin meet"
        >
          <defs>
            <marker
              id="graph-arrow"
              markerHeight="7"
              markerWidth="7"
              orient="auto"
              refX="6"
              refY="3.5"
            >
              <path d="M0,0 L7,3.5 L0,7 Z" />
            </marker>
          </defs>

          {columns.map((column, index) => (
            <g key={column.label} className="graph-column">
              <text x={105 + index * 300} y={28}>{column.label}</text>
              <line x1={105 + index * 300} x2={105 + index * 300} y1={42} y2={layout.height - 22} />
            </g>
          ))}

          <g className="graph-edges">
            {graph.edges.map((edge, index) => {
              const source = layout.positions.get(edge.source)
              const target = layout.positions.get(edge.target)
              if (!source || !target) return null
              const highlighted = affectedIds.has(edge.source) && affectedIds.has(edge.target)
              const middle = (source.x + target.x) / 2
              return (
                <path
                  className={highlighted ? 'is-highlighted' : ''}
                  d={`M ${source.x + 84} ${source.y} C ${middle} ${source.y}, ${middle} ${target.y}, ${target.x - 84} ${target.y}`}
                  key={`${edge.source}-${edge.target}-${edge.relation}-${index}`}
                  markerEnd="url(#graph-arrow)"
                >
                  <title>{`${edge.source} —${edge.relation}→ ${edge.target}${edge.evidence ? `\n${edge.evidence}` : ''}`}</title>
                </path>
              )
            })}
          </g>

          <g className="graph-nodes">
            {graph.nodes.map((node) => {
              const point = layout.positions.get(node.id)
              if (!point) return null
              const isFocus = node.id === focusId
              const isAffected = affectedIds.has(node.id)
              const className = isFocus ? 'is-focus' : isAffected ? 'is-affected' : ''
              return (
                <g
                  className={className}
                  key={node.id}
                  transform={`translate(${point.x - 84} ${point.y - 27})`}
                >
                  <rect height="54" rx="5" width="168" />
                  <text className="node-id" x="10" y="17">{node.id}</text>
                  <text className="node-label" x="10" y="37">{shortLabel(node.label)}</text>
                  <title>{`${node.id} · ${kindLabels[node.kind]}\n${node.label}`}</title>
                </g>
              )
            })}
          </g>
        </svg>
      </div>
    </div>
  )
}
