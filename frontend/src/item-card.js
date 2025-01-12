import React from 'react';
import { FileIcon, FolderIcon, Globe, Calendar, Link, Eye, EyeOff, Clock } from 'lucide-react';

const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleString();
};

const DataTable = ({ data }) => {
  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>ID</th>
            <th>Name</th>
            <th>Parent Path</th>
            <th>Parent ID</th>
            <th>Created</th>
            <th>Modified</th>
            <th>URL</th>
            <th>MIME Type</th>
            <th>Drive ID</th>
            <th>Delta</th>
            <th>Children</th>
            <th>Visibility</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr key={index}>
              <td>
                <div className="type-cell">
                  {item.directory ? (
                    <FolderIcon className="icon icon-blue" />
                  ) : (
                    <FileIcon className="icon icon-gray" />
                  )}
                  <span>{item.type || 'Unknown'}</span>
                </div>
              </td>
              <td>{item.id || '-'}</td>
              <td>{item.name || 'Unnamed'}</td>
              <td>{item.parent_path_or_name || '-'}</td>
              <td>{item.parent_id || '-'}</td>
              <td>{formatDate(item.creation_time)}</td>
              <td>{formatDate(item.last_modified_time)}</td>
              <td>
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="link">
                    View
                  </a>
                ) : (
                  '-'
                )}
              </td>
              <td>{item.mime_type || '-'}</td>
              <td>{item.drive_id || '-'}</td>
              <td>{item.delta || '-'}</td>
              <td>
                {item.children ? (
                  <div className="children-cell">
                    {item.children.map((child, childIndex) => (
                      <span key={childIndex} className="tag">
                        {child}
                      </span>
                    ))}
                  </div>
                ) : (
                  '-'
                )}
              </td>
              <td>
                <div className="visibility-cell">
                  {item.visibility !== undefined ? (
                    item.visibility ? (
                      <Eye className="icon icon-green" />
                    ) : (
                      <EyeOff className="icon icon-red" />
                    )
                  ) : (
                    '-'
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DataTable;
